"""Canonical V1.0.0 candidate identity: four native Python product wheels."""
from __future__ import annotations
import argparse, hashlib, json, re, sys
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
import v1_kroko_release as kroko  # noqa:E402
import v1_product_wheel as product  # noqa:E402
VERSION='1.0.0'; SCHEMA_VERSION=2
DISTRIBUTIONS={'free':'voice-stt-server','pro':'voice-stt-server-pro'}
PLATFORMS=('linux_x86_64','win_amd64'); IMAGE_NAMES={'free':'voice-stt-server','pro':'voice-stt-server-pro'}
_SHA40=re.compile(r'^[0-9a-f]{40}$'); _DIGEST=re.compile(r'^sha256:[0-9a-f]{64}$')
class CandidateManifestError(RuntimeError): pass

def sha256_file(path:Path)->str:
 h=hashlib.sha256();
 with Path(path).open('rb') as f:
  for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
 return h.hexdigest()

def _load_json(path:Path)->dict[str,Any]:
 try: value=json.loads(Path(path).read_text(encoding='utf-8'))
 except (OSError,ValueError) as exc: raise CandidateManifestError(f'could not read {path}: {exc}') from exc
 if not isinstance(value,dict): raise CandidateManifestError(f'{path} must contain an object')
 return value

def build_python_identity(python_dir:Path)->dict[str,Any]:
 python_dir=Path(python_dir); result={}
 for variant in ('free','pro'):
  wheels={}
  for platform in PLATFORMS:
   directory=python_dir/variant/platform; found=list(directory.glob('*.whl')) if directory.is_dir() else []
   if len(found)!=1: raise CandidateManifestError(f'expected one {variant}/{platform} product wheel, got {found}')
   report=product.inspect_product_wheel(found[0])
   if report['distribution']!=DISTRIBUTIONS[variant] or report['version']!=VERSION: raise CandidateManifestError(f'wrong product identity: {report}')
   if report['variant']!=variant: raise CandidateManifestError(f'wrong baked variant: {report}')
   if report['rootIsPurelib']: raise CandidateManifestError(f'native product wheel incorrectly marked pure: {report}')
   if not any(t.startswith('cp312-') and t.endswith('-'+platform) for t in report['tags']): raise CandidateManifestError(f'wrong product native tag: {report}')
   if report['nestedWheels'] or report['krokoDistInfoEntries'] or not report['krokoNativePayload'] or not report['variantMarkerPresent'] or not report['recordValid'] or report['modelPayloadEntries'] or report['obviousCredentialPatternMatches']: raise CandidateManifestError(f'invalid product-wheel structure: {report}')
   wheels[platform]=report
  result[variant]={'distribution':DISTRIBUTIONS[variant],'version':VERSION,'variant':variant,'wheels':wheels}
 return result

def validate_image_record(variant:str,record:dict[str,Any])->None:
 if record.get('variant')!=variant or record.get('image')!=IMAGE_NAMES[variant]: raise CandidateManifestError(f'bad OCI identity for {variant}')
 digest=str(record.get('digest') or '')
 if not _DIGEST.fullmatch(digest): raise CandidateManifestError(f'bad OCI digest for {variant}: {digest!r}')
 staging=str(record.get('stagingReference') or '')
 if not staging.endswith('@'+digest) or ':1.0.0' in staging: raise CandidateManifestError(f'staging reference not immutable/private-candidate shaped: {staging!r}')

def assemble_candidate(*,candidate_dir:Path,candidate_id:str,source_commit:str,source_tree:str,run_url:str,evidence_ref:str)->dict[str,Any]:
 candidate_dir=Path(candidate_dir)
 if not _SHA40.fullmatch(source_commit) or not _SHA40.fullmatch(source_tree): raise CandidateManifestError('invalid source commit/tree')
 python_identity=build_python_identity(candidate_dir/'python'); kroko_records={}
 for variant in ('free','pro'):
  kroko_records[variant]={}
  for platform in PLATFORMS:
   try: kroko_records[variant][platform]=kroko.verify_artifact(variant,candidate_dir/'kroko'/variant/platform,platform)
   except kroko.ReleaseKrokoError as exc: raise CandidateManifestError(str(exc)) from exc
 image_records={}
 for variant in ('free','pro'):
  record=_load_json(candidate_dir/'images'/f'{variant}.json'); validate_image_record(variant,record); image_records[variant]=record
 manifest={'schemaVersion':SCHEMA_VERSION,'productVersion':VERSION,'sourceCommit':source_commit,'sourceTree':source_tree,'candidate':{'id':candidate_id,'runUrl':run_url},'python':python_identity,'publicSdist':False,'kroko':kroko_records,'images':image_records,'qualification':{'status':'QUALIFIED','evidenceRef':evidence_ref,'publicWritesPerformed':False}}
 validate_candidate(manifest); return manifest

def validate_candidate(manifest:dict[str,Any])->None:
 if manifest.get('schemaVersion')!=SCHEMA_VERSION or manifest.get('productVersion')!=VERSION: raise CandidateManifestError('unsupported V1 candidate schema/version')
 if manifest.get('publicSdist') is not False: raise CandidateManifestError('V1.0.0 public sdist is forbidden')
 if not _SHA40.fullmatch(str(manifest.get('sourceCommit') or '')) or not _SHA40.fullmatch(str(manifest.get('sourceTree') or '')): raise CandidateManifestError('candidate source identity invalid')
 python=manifest.get('python') or {}
 if set(python)!={'free','pro'}: raise CandidateManifestError('candidate must contain Free and Pro Python distributions')
 for variant in ('free','pro'):
  entry=python[variant]
  if entry.get('distribution')!=DISTRIBUTIONS[variant] or entry.get('variant')!=variant: raise CandidateManifestError(f'bad Python distribution identity for {variant}')
  if entry.get('version')!=VERSION or set(entry.get('wheels') or {})!=set(PLATFORMS): raise CandidateManifestError(f'incomplete Python wheel matrix for {variant}')
  for platform,wheel in entry['wheels'].items():
   if not re.fullmatch(r'[0-9a-f]{64}',str(wheel.get('sha256') or '')): raise CandidateManifestError(f'missing wheel hash for {variant}/{platform}')
   if wheel.get('variant')!=variant or wheel.get('distribution')!=DISTRIBUTIONS[variant] or wheel.get('rootIsPurelib') is not False: raise CandidateManifestError(f'crossed/pure wheel identity for {variant}/{platform}')
   if wheel.get('variantMarkerPresent') is not True or wheel.get('recordValid') is not True or wheel.get('modelPayloadEntries') or wheel.get('obviousCredentialPatternMatches'): raise CandidateManifestError(f'unsafe/incomplete wheel inventory for {variant}/{platform}')
   if wheel.get('filename','').endswith('py3-none-any.whl'): raise CandidateManifestError('pure public wheel is forbidden')
 for variant in ('free','pro'):
  records=(manifest.get('kroko') or {}).get(variant) or {}
  if set(records)!=set(PLATFORMS): raise CandidateManifestError(f'incomplete Kroko provenance for {variant}')
  validate_image_record(variant,(manifest.get('images') or {}).get(variant) or {})
 q=manifest.get('qualification') or {}
 if q.get('status')!='QUALIFIED' or not q.get('evidenceRef') or q.get('publicWritesPerformed') is not False: raise CandidateManifestError('invalid qualification state')

def build_inventory(root:Path)->dict[str,Any]:
 root=Path(root).resolve(); files=[]
 for p in sorted(x for x in root.rglob('*') if x.is_file() and x.name!='sha256-inventory.json'): files.append({'path':p.relative_to(root).as_posix(),'sha256':sha256_file(p),'bytes':p.stat().st_size})
 return {'schemaVersion':1,'files':files}

def main(argv=None):
 p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
 a=sub.add_parser('assemble'); a.add_argument('--candidate-dir',type=Path,required=True); a.add_argument('--candidate-id',required=True); a.add_argument('--source-commit',required=True); a.add_argument('--source-tree',required=True); a.add_argument('--run-url',required=True); a.add_argument('--evidence-ref',required=True); a.add_argument('--out',type=Path,required=True)
 v=sub.add_parser('validate'); v.add_argument('manifest',type=Path)
 i=sub.add_parser('inventory'); i.add_argument('--candidate-dir',type=Path,required=True); i.add_argument('--out',type=Path,required=True)
 args=p.parse_args(argv)
 try:
  if args.command=='assemble':
   data=assemble_candidate(candidate_dir=args.candidate_dir,candidate_id=args.candidate_id,source_commit=args.source_commit,source_tree=args.source_tree,run_url=args.run_url,evidence_ref=args.evidence_ref); args.out.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')
  elif args.command=='validate': validate_candidate(_load_json(args.manifest))
  else: args.out.write_text(json.dumps(build_inventory(args.candidate_dir),indent=2,sort_keys=True)+'\n',encoding='utf-8')
 except CandidateManifestError as exc: print(f'ERROR: {exc}',file=sys.stderr); return 1
 return 0
if __name__=='__main__': raise SystemExit(main())
