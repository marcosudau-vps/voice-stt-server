import importlib.util, json, os, sys, tempfile, threading, time, traceback
SRC="/home/marco/w5r02c3-native-src"; sys.path.insert(0, SRC)
from api_fastapi_server.server import ServerSettings, create_app
from fastapi.testclient import TestClient
spec=importlib.util.spec_from_file_location("_t", os.path.join(SRC,"tests","unit","test_fastapi_server_multi_user.py"))
T=importlib.util.module_from_spec(spec); sys.modules["_t"]=T; spec.loader.exec_module(T)
hits=[]
with tempfile.TemporaryDirectory() as d:
    app=create_app(ServerSettings(model_warmup=False,data_root_path=d,admin_api_key="k",
        request_log_stdout=False,performance_log_stdout=False),
        scheduler_factory=T.AutoScheduler, recorder_factory=T.FakeRecorder)
    with TestClient(app) as c:
        e=app.state.voicestt_service.events
        real=e._set_store_state
        def traced(state,*,error=None):
            prev=e._store_state              # direct read, no store I/O
            real(state,error=error)
            if prev!=state:
                hits.append({"from":prev,"to":state,"thread":threading.current_thread().name,
                             "stack":[l.strip().replace("\n"," | ") for l in traceback.format_stack()[:-1]][-6:]})
        e._set_store_state=traced
        e._store.append = lambda ev: (_ for _ in ()).throw(OSError("simulated outage"))
        e.emit("system","outage.not_committed")
        t0=time.monotonic(); ready=0; total=0
        while time.monotonic()-t0 < 1.5:
            total+=1
            if e._store_state=="ready": ready+=1
            time.sleep(0.0005)
        print(json.dumps({"samples":total,"ready":ready,"final":e._store_state,"transitions":len(hits)}))
        for h in hits:
            print(f"--- {h['from']} -> {h['to']} thread={h['thread']}")
            for l in h["stack"]: print("   ",l)
        e._set_store_state=real
