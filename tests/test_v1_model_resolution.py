from pathlib import Path
import pytest
from VoiceSTT.transcription_engines.base import TranscriptionEngineError
from VoiceSTT.transcription_engines import model_resolver

def _ct2(path:Path):path.mkdir(parents=True);(path/'config.json').write_text('{}');(path/'model.bin').write_bytes(b'x');return path
def test_faster_whisper_default_download_is_false(monkeypatch,tmp_path):
 monkeypatch.delenv(model_resolver.FASTER_WHISPER_AUTO_DOWNLOAD_ENV,raising=False);monkeypatch.setenv(model_resolver.FASTER_WHISPER_ROOT_ENV,str(tmp_path))
 with pytest.raises(TranscriptionEngineError,match='disabled by default'):model_resolver.resolve_faster_whisper_model('small')
def test_faster_whisper_allowlist_and_local_path(monkeypatch,tmp_path):
 monkeypatch.setenv(model_resolver.FASTER_WHISPER_ROOT_ENV,str(tmp_path));assert model_resolver.resolve_faster_whisper_model('large_turbo',options={'auto_download_model':True})==model_resolver.FASTER_WHISPER_MODEL_REGISTRY['large_turbo']
 with pytest.raises(TranscriptionEngineError,match='reviewed aliases'):model_resolver.resolve_faster_whisper_model('vendor/custom',options={'auto_download_model':True})
 model=_ct2(tmp_path/'local');assert model_resolver.resolve_faster_whisper_model(str(model))==str(model.resolve())
def test_baked_distribution_variant_is_default_and_key_is_not_signal(monkeypatch):
 monkeypatch.setattr(model_resolver,'BAKED_KROKO_VARIANT','pro');monkeypatch.delenv(model_resolver.KROKO_VARIANT_ENV,raising=False);monkeypatch.setenv('KROKO_API_KEY','does-not-select-variant');assert model_resolver.installed_kroko_variant()=='pro';assert model_resolver.installed_kroko_variant({'runtime_variant':'free'})=='free'
def test_pro_missing_model_is_fail_closed_with_guidance(monkeypatch,tmp_path):
 monkeypatch.setattr(model_resolver,'BAKED_KROKO_VARIANT','pro');monkeypatch.delenv(model_resolver.KROKO_VARIANT_ENV,raising=False);monkeypatch.setenv(model_resolver.KROKO_ROOT_ENV,str(tmp_path))
 with pytest.raises(TranscriptionEngineError) as exc:model_resolver.resolve_kroko_model('Kroko-DE-Pro-64-L-Streaming-001.data')
 text=str(exc.value);assert 'never' in text.lower() and 'download' in text.lower();assert 'Community models are not used' in text;assert model_resolver.KROKO_ROOT_ENV in text and 'KROKO_API_KEY' in text and 'https://kroko.ai/' in text
def test_pro_explicit_local_model_is_allowed(monkeypatch,tmp_path):
 monkeypatch.setattr(model_resolver,'BAKED_KROKO_VARIANT','pro');model=tmp_path/'licensed.data';model.write_bytes(b'licensed');assert model_resolver.resolve_kroko_model(str(model))==str(model.resolve())
def test_pro_model_directory_never_selects_community_fallback(monkeypatch,tmp_path):
 monkeypatch.setattr(model_resolver,'BAKED_KROKO_VARIANT','pro');community=tmp_path/'Kroko-DE-Community-64-L-Streaming-001.data';community.write_bytes(b'community')
 with pytest.raises(TranscriptionEngineError,match='Community models are not used'):model_resolver.resolve_kroko_model('missing-pro.data',options={'model_dir':str(tmp_path)})
def test_free_remote_source_is_pinned_and_custom_sources_are_rejected(monkeypatch,tmp_path):
 monkeypatch.setattr(model_resolver,'BAKED_KROKO_VARIANT','free');monkeypatch.setenv(model_resolver.KROKO_ROOT_ENV,str(tmp_path));name='Kroko-DE-Community-64-L-Streaming-001.data'
 options={}; assert model_resolver.resolve_kroko_model(name,options=options).endswith(name); assert options['model_repo_id']==model_resolver.KROKO_FREE_REPO; assert options['model_revision']==model_resolver.KROKO_FREE_REVISION
 for opts in ({'model_repo_id':'evil/repo'},{'model_download_url':'https://example.invalid/model'},{'model_revision':'main'}):
  with pytest.raises(TranscriptionEngineError):model_resolver.resolve_kroko_model(name,options=opts)
def test_public_default_model_root_has_no_repository_or_personal_path(monkeypatch):
 monkeypatch.delenv(model_resolver.KROKO_ROOT_ENV,raising=False);root=str(model_resolver.default_kroko_model_root());assert 'voice-stt-server' not in root.lower()
