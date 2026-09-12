"""Local V1 correction acceptance runner for Windows x64 or Linux x86_64.

Additional operator acceptance only; never release authority.
"""
from __future__ import annotations
import argparse, json, os, platform as host_platform, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(cmd,*,cwd=ROOT,env=None,log=None,expect=None):
 printable=subprocess.list2cmdline([str(x) for x in cmd]); print('+',printable)
 cp=subprocess.run([str(x) for x in cmd],cwd=str(cwd),env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 print(cp.stdout,end='')
 if log:
  with Path(log).open('a',encoding='utf-8') as f: f.write('+ '+printable+'\n'+cp.stdout+'\nexit_code='+str(cp.returncode)+'\n')
 if expect is None and cp.returncode: raise SystemExit(cp.returncode)
 if expect is not None and cp.returncode!=expect: raise SystemExit(f'{printable}: expected {expect}, got {cp.returncode}')
 return cp

def target_platform():
 machine=host_platform.machine().lower()
 if os.name=='nt' and machine in {'amd64','x86_64'}: return 'win_amd64'
 if sys.platform.startswith('linux') and machine in {'x86_64','amd64'}: return 'linux_x86_64'
 raise SystemExit(f'unsupported acceptance host: {sys.platform}/{host_platform.machine()}')

def clean_venv(variant,wheel,work,log):
 venv=work/f'venv-{variant}'
 if venv.exists(): shutil.rmtree(venv)
 run([sys.executable,'-m','venv',str(venv)],log=log)
 py=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python'); stt=venv/('Scripts/stt-server.exe' if os.name=='nt' else 'bin/stt-server')
 run([py,'-m','pip','install','--upgrade','pip'],log=log); run([py,'-m','pip','install',str(wheel)],log=log)
 run([py,'-c',"import VoiceSTT, VoiceSTT_server.server, kroko_onnx; from VoiceSTT._release_variant import KROKO_VARIANT; print('variant='+KROKO_VARIANT); assert KROKO_VARIANT == '"+variant+"'"],log=log)
 run([stt,'--help'],log=log); run([py,'-m','pip','check'],log=log); run([py,'-m','pip','list'],log=log)
 if variant=='pro':
  env=os.environ.copy(); env.pop('VOICESTT_KROKO_VARIANT',None); env.pop('KROKO_API_KEY',None); env['VOICESTT_KROKO_MODEL_ROOT']=str(work/'definitely-empty-pro-model-root'); Path(env['VOICESTT_KROKO_MODEL_ROOT']).mkdir(exist_ok=True)
  code="from VoiceSTT._release_variant import KROKO_VARIANT; from VoiceSTT.transcription_engines.model_resolver import default_kroko_model_root,resolve_kroko_model; from VoiceSTT.transcription_engines.base import TranscriptionEngineError; print('variant='+KROKO_VARIANT); print('default_root='+str(default_kroko_model_root()));\ntry: resolve_kroko_model('Kroko-DE-Pro-64-L-Streaming-001.data')\nexcept TranscriptionEngineError as e: print(str(e)); raise SystemExit(2)\nraise SystemExit(99)"
  cp=run([py,'-c',code],env=env,log=log,expect=2)
  if 'Traceback' in cp.stdout or 'Community models are not used' not in cp.stdout or 'KROKO_API_KEY' not in cp.stdout: raise SystemExit('Pro missing-model UX evidence failed')

def main(argv=None):
 p=argparse.ArgumentParser(description='Build and clean-install both V1 product variants locally'); p.add_argument('--work-dir',type=Path,default=ROOT/'.v1-local-acceptance'); p.add_argument('--keep',action='store_true'); args=p.parse_args(argv)
 if sys.version_info[:2]!=(3,12): raise SystemExit('V1 product acceptance requires CPython 3.12')
 target=target_platform(); work=args.work_dir.resolve()
 if work.exists() and not args.keep: shutil.rmtree(work)
 work.mkdir(parents=True,exist_ok=True); summary={'platform':target,'python':sys.version,'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'variants':{}}
 for variant in ('free','pro'):
  log=work/f'{target}-{variant}.log'; kroko_dir=work/'kroko'/variant; product_dir=work/'product'/variant
  run([sys.executable,'tools/v1_kroko_release.py','build','--variant',variant,'--platform',target,'--out-dir',kroko_dir],log=log)
  kroko_wheels=list(kroko_dir.glob('*.whl'))
  if len(kroko_wheels)!=1: raise SystemExit(f'expected one Kroko wheel: {kroko_wheels}')
  report=product_dir/'product.json'; run([sys.executable,'tools/v1_product_wheel.py','build','--variant',variant,'--platform',target,'--kroko-wheel',kroko_wheels[0],'--out-dir',product_dir,'--report',report],log=log)
  wheels=list(product_dir.glob('*.whl'))
  if len(wheels)!=1: raise SystemExit(f'expected one product wheel: {wheels}')
  clean_venv(variant,wheels[0],work,log); summary['variants'][variant]=json.loads(report.read_text(encoding='utf-8'))
 (work/'acceptance-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(summary,indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
