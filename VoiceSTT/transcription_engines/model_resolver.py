"""Resolve V1 ASR models without unsafe implicit downloads."""
import os, sys
from pathlib import Path
from VoiceSTT._release_variant import KROKO_VARIANT as BAKED_KROKO_VARIANT
from .base import TranscriptionEngineError
TRUE_VALUES={"1","true","yes","on"}; FASTER_WHISPER_ROOT_ENV="VOICESTT_FASTER_WHISPER_MODEL_ROOT"; FASTER_WHISPER_AUTO_DOWNLOAD_ENV="VOICESTT_FASTER_WHISPER_AUTO_DOWNLOAD"; KROKO_ROOT_ENV="VOICESTT_KROKO_MODEL_ROOT"; KROKO_VARIANT_ENV="VOICESTT_KROKO_VARIANT"; OFFLINE_MODELS_ENV="VOICESTT_OFFLINE_MODELS"; KROKO_HOME_URL="https://kroko.ai/"
KROKO_FREE_REPO="Banafo/Kroko-ASR"; KROKO_FREE_REVISION="d45212aeb212dd66083dd22710c9954f40ff8cc1"
FASTER_WHISPER_MODEL_REGISTRY={"tiny":"Systran/faster-whisper-tiny","base":"Systran/faster-whisper-base","small":"Systran/faster-whisper-small","medium":"Systran/faster-whisper-medium","large":"Systran/faster-whisper-large-v3","large_turbo":"deepdml/faster-whisper-large-v3-turbo-ct2"}
KROKO_FREE_MODEL_REGISTRY={"Kroko-DE-Community-64-L-Streaming-001.data","Kroko-DE-Community-128-L-Streaming-001.data","Kroko-EN-Community-64-L-Streaming-001.data","Kroko-EN-Community-128-L-Streaming-001.data"}
def _bool(value,default=False):
 if value is None:return default
 if isinstance(value,str):return value.strip().lower() in TRUE_VALUES
 return bool(value)
def offline_models_enabled(options=None):
 options=options or {}
 if "local_files_only" in options:return _bool(options["local_files_only"])
 if "offline_models" in options:return _bool(options["offline_models"])
 return _bool(os.getenv(OFFLINE_MODELS_ENV),False)
def faster_whisper_auto_download_enabled(options=None):
 options=options or {}
 if "auto_download_model" in options:return _bool(options["auto_download_model"],False)
 if "download_model" in options:return _bool(options["download_model"],False)
 return _bool(os.getenv(FASTER_WHISPER_AUTO_DOWNLOAD_ENV),False)
def installed_kroko_variant(options=None):
 options=options or {}; value=options.get("runtime_variant") or os.getenv(KROKO_VARIANT_ENV) or BAKED_KROKO_VARIANT; value=str(value).strip().lower()
 if value not in {"free","pro"}:raise TranscriptionEngineError("Invalid Kroko runtime variant %r; expected 'free' or 'pro'."%value)
 return value
def default_kroko_model_root():
 if os.name=="nt":
  root=os.getenv("LOCALAPPDATA")
  if root:return Path(root)/"VoiceSTT"/"models"/"kroko"
 if sys.platform=="darwin":return Path.home()/"Library"/"Application Support"/"VoiceSTT"/"models"/"kroko"
 root=os.getenv("XDG_DATA_HOME")
 if root:return Path(root)/"VoiceSTT"/"models"/"kroko"
 return Path.home()/".local"/"share"/"VoiceSTT"/"models"/"kroko"
def validate_kroko_download_policy(filename,options=None):
 options=options or {}; variant=installed_kroko_variant(options)
 if variant=="pro":raise TranscriptionEngineError("Kroko Pro models are never downloaded automatically; provision the licensed model locally.")
 if filename not in KROKO_FREE_MODEL_REGISTRY:raise TranscriptionEngineError("Automatic Kroko Community download only accepts registered V1 Community models.")
 if options.get("model_download_url"):raise TranscriptionEngineError("Custom Kroko model_download_url is not allowed by the V1 Community download policy; use an explicit local .data file instead.")
 repo=options.get("model_repo_id") or options.get("hf_repo_id")
 if repo and repo!=KROKO_FREE_REPO:raise TranscriptionEngineError("Custom Kroko Hugging Face repositories are not allowed by the V1 Community download policy; use an explicit local .data file instead.")
 revision=options.get("model_revision") or options.get("hf_revision")
 if revision and revision!=KROKO_FREE_REVISION:raise TranscriptionEngineError("Custom Kroko model revisions are not allowed by the V1 Community download policy.")
 return KROKO_FREE_REPO,KROKO_FREE_REVISION
def _is_ctranslate2_model(path):return path.is_dir() and (path/"config.json").is_file() and (path/"model.bin").is_file()
def _snapshot_model(path):
 if _is_ctranslate2_model(path):return path
 snapshots=path/"snapshots"
 if snapshots.is_dir():
  for candidate in sorted(snapshots.iterdir(),reverse=True):
   if _is_ctranslate2_model(candidate):return candidate
 return None
def _normalized_faster_whisper_alias(value):
 alias=str(value).strip().lower().replace("-","_")
 if alias=="large_v3":return "large"
 if alias in {"large_v3_turbo","large_turbo"}:return "large_turbo"
 return alias
def _model_aliases(model):
 value=str(model).strip(); normalized=value.lower().replace("_","-"); aliases=[value]
 if normalized.startswith("models--"):aliases.append(normalized)
 else:aliases.extend([f"models--Systran--faster-whisper-{normalized}",f"faster-whisper-{normalized}",normalized])
 return list(dict.fromkeys(aliases))
def resolve_faster_whisper_model(model,download_root=None,options=None):
 options=dict(options or {}); value=str(model).strip(); direct=Path(value).expanduser(); resolved=_snapshot_model(direct)
 if resolved is not None:return str(resolved.resolve())
 roots=[options.get("model_root"),os.getenv(FASTER_WHISPER_ROOT_ENV),download_root]; checked=[]
 for root_value in roots:
  if not root_value:continue
  root=Path(str(root_value)).expanduser()
  for alias in _model_aliases(value):
   candidate=root/alias; checked.append(str(candidate)); resolved=_snapshot_model(candidate)
   if resolved is not None:return str(resolved.resolve())
  if root.is_dir():
   suffix=value.lower().replace("_","-")
   for candidate in sorted(root.glob("models--*--*")):
    if candidate.name.lower().endswith(suffix):
     checked.append(str(candidate)); resolved=_snapshot_model(candidate)
     if resolved is not None:return str(resolved.resolve())
 locations=", ".join(checked) if checked else value
 if offline_models_enabled(options) or not faster_whisper_auto_download_enabled(options):raise TranscriptionEngineError("faster-whisper model '%s' was not found locally and automatic model download is disabled by default. Checked: %s. Set %s to the mounted CTranslate2 model root or pass an absolute model directory. To opt in to a reviewed model download, set engine option auto_download_model=true or %s=1."%(value,locations,FASTER_WHISPER_ROOT_ENV,FASTER_WHISPER_AUTO_DOWNLOAD_ENV))
 alias=_normalized_faster_whisper_alias(value); repo_id=FASTER_WHISPER_MODEL_REGISTRY.get(alias)
 if repo_id is None:raise TranscriptionEngineError("Automatic faster-whisper download only accepts reviewed aliases: %s. Requested '%s'. Use a local absolute model directory for any other model."%(", ".join(FASTER_WHISPER_MODEL_REGISTRY),value))
 return repo_id
def resolve_kroko_model(model,download_root=None,options=None):
 # Preserve the caller dictionary intentionally: KrokoOnnxBackend subsequently
 # uses the same engine_options object for its actual downloader. After policy
 # validation we bind the immutable Community source/revision into it.
 options = options if isinstance(options,dict) else {}
 variant=installed_kroko_variant(options); explicit=options.get("model_path") or options.get("model_file"); value=explicit or model; path=Path(str(value)).expanduser()
 if path.is_file():return str(path.resolve())
 default_root=default_kroko_model_root(); roots=[options.get("model_root"),options.get("model_dir"),os.getenv(KROKO_ROOT_ENV),download_root,default_root]; checked=[]
 for root_value in roots:
  if not root_value:continue
  root=Path(str(root_value)).expanduser(); candidate=root/path.name; checked.append(str(candidate))
  if candidate.is_file():
   if variant=="pro" and path.name in KROKO_FREE_MODEL_REGISTRY and not explicit:continue
   return str(candidate.resolve())
 locations=", ".join(dict.fromkeys(checked)) if checked else str(path)
 if variant=="pro":raise TranscriptionEngineError("Kroko Pro runtime is installed, but no compatible licensed Pro model was found. The runtime is already present; Pro models are never downloaded automatically and Community models are not used as a Pro fallback. Expected local model: %s. Default model directory: %s. Set %s or pass engine_options['model_path']. KROKO_API_KEY is a runtime credential only. Checked: %s. Kroko licensing/model source: %s"%(path.name,default_root,KROKO_ROOT_ENV,locations,KROKO_HOME_URL))
 if offline_models_enabled(options):raise TranscriptionEngineError("Offline model mode is enabled and Kroko Community model '%s' was not found. Checked: %s. Set %s or pass an absolute .data file."%(path.name,locations,KROKO_ROOT_ENV))
 repo,revision=validate_kroko_download_policy(path.name,options)
 options.pop("model_download_url",None); options.pop("hf_repo_id",None); options.pop("hf_revision",None); options["model_repo_id"]=repo; options["model_revision"]=revision
 return str(default_root/path.name)
