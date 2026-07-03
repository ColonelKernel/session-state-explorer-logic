import json

from logic_session_evidence_explorer import manifest_loader, utils


def test_manifest_json_loads():
    text = json.dumps({
        "schema_version": "0.1.0",
        "session_name": "My Logic Demo",
        "daw_name": "Logic Pro",
        "daw_version": "11",
        "audio_files": [{"file_name": "01_Lead_Vocal.wav", "role": "Vocal", "notes": "printed"}],
        "notes": "post-fader stems",
    })
    result = manifest_loader.load_manifest_text(text)
    assert result.session_name == "My Logic Demo"
    assert result.daw_version == "11"


def test_role_overrides_applied():
    text = json.dumps({
        "audio_files": [{"file_name": "02_Bass.wav", "role": "Bass"}],
    })
    result = manifest_loader.load_manifest_text(text)
    assert result.role_overrides == {"02_Bass.wav": "Bass"}


def test_unknown_fields_warn_but_do_not_crash():
    text = json.dumps({
        "session_name": "X",
        "totally_unknown": 123,
        "audio_files": [{"file_name": "a.wav", "mystery": True}],
    })
    result = manifest_loader.load_manifest_text(text)
    assert any("totally_unknown" in w for w in result.warnings)
    assert any("mystery" in w for w in result.warnings)
    assert result.session_name == "X"


def test_channel_strip_notes_csv():
    utils.reset_ids()
    csv_text = (
        "track_name,role,plugins,sends,bus,notes\n"
        'Lead Vocal,Vocal,"Channel EQ; Compressor","Vocal Verb","Vocal Bus","chain"\n'
    )
    notes, warnings = manifest_loader.load_channel_strip_notes(csv_text, file_name="notes.csv")
    assert len(notes) == 1
    assert notes[0].track_name == "Lead Vocal"
    assert notes[0].plugins == ["Channel EQ", "Compressor"]
    assert notes[0].sends == ["Vocal Verb"]
    assert notes[0].bus == "Vocal Bus"


def test_channel_strip_notes_json():
    utils.reset_ids()
    text = json.dumps([
        {"track_name": "Drums", "role": "Drums", "plugins": ["EQ", "Comp"], "bus": "Drum Bus"},
    ])
    notes, warnings = manifest_loader.load_channel_strip_notes(text, file_name="notes.json")
    assert len(notes) == 1
    assert notes[0].plugins == ["EQ", "Comp"]
