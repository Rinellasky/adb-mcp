# Live verification driver for Premiere Phase 1 (Technical_Roadmap_Premiere.md)
# Imports pr-mcp.py and calls tool functions directly (full path through the
# proxy to the UXP plugin). Run stages separately to keep runs short:
#   uv run python ../scripts/live_test_pr_phase1.py <stage>   (cwd: mcp/)
# Stages: smoke, build, effects, timeline, audio

import importlib.util as u
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "mcp"))

spec = u.spec_from_file_location("prmcp", "pr-mcp.py")
m = u.module_from_spec(spec)
spec.loader.exec_module(m)

MEDIA = ["F:\\premier\\media\\clipA.mp4", "F:\\premier\\media\\clipB.mp4"]
SEQ_NAME = "phase1_test"


def show(label, result, keys=None):
    print(f"\n=== {label} ===")
    if isinstance(result, dict):
        if "status" not in result:
            # python-side tool result (no proxy envelope) - print raw
            print(json.dumps(result, indent=1, default=str)[:3000])
            return result
        status = result.get("status")
        print(f"status: {status}")
        if status == "FAILURE":
            print(f"message: {result.get('message')}")
            return result
        r = result.get("response")
        if keys and isinstance(r, dict):
            r = {k: r.get(k) for k in keys}
        print(json.dumps(r, indent=1, default=str)[:3000])
    else:
        print(str(result)[:2000])
    return result


def get_seq_id(result=None):
    if result is None:
        result = m.get_project_info()
    for s in result.get("sequences", []):
        if s.get("name") == SEQ_NAME:
            return s["id"]
    return None


def stage_smoke():
    show("get_project_info (health check)", m.get_project_info())


def stage_build():
    show("import_media", m.import_media(MEDIA))
    r = m.create_sequence_from_media(["clipA.mp4", "clipB.mp4"], SEQ_NAME)
    show("create_sequence_from_media", r)
    seq = get_seq_id(r)
    print(f"\nsequence id: {seq}")
    show("get_track_count", m.get_track_count(seq))
    show("get_sequence_details", m.get_sequence_details(seq, include_effects=False))


def stage_effects():
    seq = get_seq_id()
    r = show("list_video_effects", m.list_video_effects())
    effects = (r.get("response") or {}).get("effects") or []
    print(f"video effect count: {len(effects)}")
    print("gaussian present:", "AE.ADBE Gaussian Blur 2" in effects)

    r = show("list_audio_effects", m.list_audio_effects())
    aeffects = (r.get("response") or {}).get("effects") or []
    print(f"audio effect count: {len(aeffects)}")

    show("add_video_effect (gaussian, Blurriness=40)",
         m.add_video_effect(seq, 0, 0, "AE.ADBE Gaussian Blur 2",
                            [{"name": "Blurriness", "value": 40}]))

    r = m.get_clip_effects(seq, 0, 0, "VIDEO")
    fx = (r.get("response") or {}).get("effects") or []
    print("\n=== get_clip_effects: chain matchNames ===")
    for c in fx:
        print(" ", c.get("matchName"))
        if c.get("matchName") == "AE.ADBE Gaussian Blur 2":
            for p in c.get("params", []):
                print("    param:", p.get("name"), "=", p.get("value"))

    show("set_effect_parameter (Blurriness=80)",
         m.set_effect_parameter(seq, 0, 0, "VIDEO",
                                "AE.ADBE Gaussian Blur 2", "Blurriness", 80))

    r = m.get_clip_effects(seq, 0, 0, "VIDEO")
    for c in (r.get("response") or {}).get("effects") or []:
        if c.get("matchName") == "AE.ADBE Gaussian Blur 2":
            for p in c.get("params", []):
                if p.get("name") == "Blurriness":
                    print("verify Blurriness after set:", p.get("value"))

    show("set_clip_transform (scale=50, pos 0.25/0.25)",
         m.set_clip_transform(seq, 0, 0, position={"x": 0.25, "y": 0.25}, scale=50))

    show("set_clip_crop (left=10)", m.set_clip_crop(seq, 0, 0, left=10))

    show("remove_effect (gaussian)",
         m.remove_effect(seq, 0, 0, "VIDEO", "AE.ADBE Gaussian Blur 2"))

    r = m.get_clip_effects(seq, 0, 0, "VIDEO")
    names = [c.get("matchName") for c in (r.get("response") or {}).get("effects") or []]
    print("verify gaussian removed:", "AE.ADBE Gaussian Blur 2" not in names)


def stage_timeline():
    seq = get_seq_id()

    # clipB is the last clip (10-20s): split at 15s - no downstream clip to damage
    show("split_clip (clip 1 at 15s)", m.split_clip(seq, 0, 1, "VIDEO", 15.0))

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0), {})
    print("V1 clips after split:", [(c["name"], c["startSeconds"], c["endSeconds"]) for c in v0.get("clips", [])])

    show("clone_clip (clip 0 -> V2, same time)",
         m.clone_clip(seq, 0, 0, "VIDEO", 0.0, video_track_offset=1, audio_track_offset=1, insert=False))

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v1 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 1), None)
    clips_v1 = v1.get("clips", []) if v1 else []
    print("V2 clips after clone:", [(c["name"], c["startSeconds"]) for c in clips_v1])

    if clips_v1:
        show("move_clip (V2 clip 0 -> 30s)", m.move_clip(seq, 1, 0, "VIDEO", 30.0))
        r = m.get_sequence_details(seq, include_effects=False)
        tracks = (r.get("response") or {}).get("tracks") or []
        v1 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 1), None)
        print("V2 clips after move:", [(c["name"], c["startSeconds"]) for c in (v1.get("clips", []) if v1 else [])])

        show("select_clips (V2 clip 0)",
             m.select_clips(seq, [{"trackIndex": 1, "trackItemIndex": 0, "trackType": "VIDEO"}]))
        show("get_selected_clips", m.get_selected_clips(seq))

        show("remove_clips (V2 clip 0, no ripple)",
             m.remove_clips(seq, [{"trackIndex": 1, "trackItemIndex": 0, "trackType": "VIDEO"}], ripple_delete=False))
        r = m.get_sequence_details(seq, include_effects=False)
        tracks = (r.get("response") or {}).get("tracks") or []
        v1 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 1), None)
        print("V2 clips after remove:", [(c["name"], c["startSeconds"]) for c in (v1.get("clips", []) if v1 else [])])

    show("insert_clip_at_time (clipA at 50s V1/A1)",
         m.insert_clip_at_time(seq, "clipA.mp4", 50.0, 0, 0))
    show("overwrite_clip_at_time (clipB at 52s V1/A1)",
         m.overwrite_clip_at_time(seq, "clipB.mp4", 52.0, 0, 0))

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0), {})
    print("V1 clips after insert+overwrite:", [(c["name"], c["startSeconds"], c["endSeconds"]) for c in v0.get("clips", [])])


def stage_audio():
    seq = get_seq_id()

    show("get_audio_clip_info (A1 clip 0, before)",
         m.get_audio_clip_info(seq, 0, 0), keys=["name", "volume", "pan"])

    show("set_clip_volume (-6 dB)", m.set_clip_volume(seq, 0, 0, level_db=-6.0))

    r = m.get_audio_clip_info(seq, 0, 0)
    vol = (r.get("response") or {}).get("volume")
    print("verify volume after -6dB:", json.dumps(vol, default=str))

    show("set_clip_pan (balance=-50)", m.set_clip_pan(seq, 0, 0, -50.0))
    r = m.get_audio_clip_info(seq, 0, 0)
    print("verify pan:", json.dumps((r.get("response") or {}).get("pan"), default=str))

    show("fade_audio_in (1s)", m.fade_audio_in(seq, 0, 0, 1.0))
    show("fade_audio_out (1s)", m.fade_audio_out(seq, 0, 0, 1.0))

    show("add_audio_transition (Constant Power)",
         m.add_audio_transition(seq, 0, 0, "Constant Power", 1.0, 0.5))

    show("set_audio_track_locked (A1, True)",
         m.set_audio_track_locked(seq, 0, True))

    show("save_project", m.save_project())


def stage_retest():
    """Retest after fixes: AECrop matchName, split composite, dB mapping, stereo pan."""
    seq = get_seq_id()

    # -- effects fixes --
    show("set_clip_crop (left=10) [AECrop fix]", m.set_clip_crop(seq, 0, 0, left=10))

    show("remove_effect (gaussian) [untested earlier]",
         m.remove_effect(seq, 0, 0, "VIDEO", "AE.ADBE Gaussian Blur 2"))
    r = m.get_clip_effects(seq, 0, 0, "VIDEO")
    names = [c.get("matchName") for c in (r.get("response") or {}).get("effects") or []]
    print("chain after remove:", names)
    print("verify gaussian removed:", "AE.ADBE Gaussian Blur 2" not in names)

    # -- stereo clip for audio tests --
    show("import clipC_stereo", m.import_media(["F:\\premier\\media\\clipC_stereo.mp4"]))
    show("overwrite clipC at 70s", m.overwrite_clip_at_time(seq, "clipC_stereo.mp4", 70.0, 0, 0))

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next(t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0)
    a0 = next(t for t in tracks if t["trackType"] == "AUDIO" and t["trackIndex"] == 0)
    vC = next(i for i, c in enumerate(v0["clips"]) if c["startSeconds"] == 70)
    aC = next(i for i, c in enumerate(a0["clips"]) if c["startSeconds"] == 70)
    print(f"clipC indices: video={vC}, audio={aC}")

    # -- split fix (clipC is the last clip; safe) --
    show("split_clip (clipC at 74s) [setInPoint+move fix]",
         m.split_clip(seq, 0, vC, "VIDEO", 74.0))
    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next(t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0)
    pieces = [(c["startSeconds"], c["endSeconds"], c["inPointSeconds"]) for c in v0["clips"] if c["startSeconds"] >= 69]
    print("clipC pieces after split (start, end, inPoint):", pieces)
    ok = pieces == [(70, 74, 0), (74, 78, 4)]
    print("verify split correct:", ok)

    # -- audio fixes (stereo clip) --
    show("get_audio_clip_info (clipC, before)", m.get_audio_clip_info(seq, 0, aC),
         keys=["name", "volume", "pan"])

    show("set_clip_volume (-6 dB UI) [mapping fix]", m.set_clip_volume(seq, 0, aC, level_db=-6.0))
    r = m.get_audio_clip_info(seq, 0, aC)
    vol = (r.get("response") or {}).get("volume") or {}
    print("verify volume: raw =", vol.get("rawValue"), "approxDb =", vol.get("approxDb"),
          "(expect raw ~0.0891, approxDb ~ -6.0)")

    show("set_clip_pan (-50) [stereo]", m.set_clip_pan(seq, 0, aC, -50.0))
    r = m.get_audio_clip_info(seq, 0, aC)
    print("verify pan:", json.dumps((r.get("response") or {}).get("pan"), default=str))

    show("fade_audio_in (1s)", m.fade_audio_in(seq, 0, aC, 1.0))
    r = m.get_audio_clip_info(seq, 0, aC)
    vol = (r.get("response") or {}).get("volume") or {}
    print("verify timeVarying after fade:", vol.get("timeVarying"))

    try:
        show("add_audio_transition (feature-detect)",
             m.add_audio_transition(seq, 0, aC, "Constant Power", 1.0, 0.5))
    except Exception as e:
        print(f"add_audio_transition -> {e}")

    try:
        show("set_audio_track_locked (feature-detect)", m.set_audio_track_locked(seq, 0, True))
    except Exception as e:
        print(f"set_audio_track_locked -> {e}")

    show("save_project", m.save_project())


# ---------------------------------------------------------------------------
# Phase 2 stages (sequence: stereo_test for keyframes/lumetri, phase1_test for
# markers/metadata)
# ---------------------------------------------------------------------------

STEREO_SEQ = "stereo_test"


def get_named_seq_id(name):
    r = m.get_project_info()
    for s in r.get("sequences", []):
        if s.get("name") == name:
            return s["id"]
    return None


def stage_keyframes():
    seq = get_named_seq_id(STEREO_SEQ)

    # animate Motion Scale with a batch (clip spans 0-8s)
    show("add_keyframes (Scale 100->150->100, mixed interp)",
         m.add_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale", [
             {"timeSeconds": 0.0, "value": 100},
             {"timeSeconds": 4.0, "value": 150, "interpolation": "BEZIER"},
             {"timeSeconds": 8.0, "value": 100, "interpolation": "HOLD"},
         ]))

    r = show("get_keyframes (Scale)",
             m.get_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale"))
    kfs = (r.get("response") or {}).get("keyframes") or []
    print("keyframe times/values:", [(k.get("timeSeconds"), k.get("value"), k.get("temporalInterpolationMode")) for k in kfs])
    print("verify 3 keyframes:", len(kfs) == 3)

    show("remove_keyframe (t=4)",
         m.remove_keyframe(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale", 4.0))
    r = m.get_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale")
    print("after remove:", len((r.get("response") or {}).get("keyframes") or []))

    show("clear_keyframes (Scale)",
         m.clear_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale"))
    r = m.get_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Scale")
    resp = r.get("response") or {}
    print("after clear: count =", len(resp.get("keyframes") or []),
          "timeVarying =", resp.get("timeVarying"))

    show("fade_video_in (1s)", m.fade_video_in(seq, 0, 0, 1.0))
    show("fade_video_out (1s)", m.fade_video_out(seq, 0, 0, 1.0))
    r = m.get_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Opacity", "Opacity")
    kfs = (r.get("response") or {}).get("keyframes") or []
    print("opacity keyframes:", [(k.get("timeSeconds"), k.get("value")) for k in kfs])

    show("ken_burns (zoom 100->130 + pan, eased)",
         m.ken_burns(seq, 0, 0, start_scale=100, end_scale=130,
                     start_position={"x": 0.5, "y": 0.5},
                     end_position={"x": 0.45, "y": 0.45}, ease=True))
    r = m.get_keyframes(seq, 0, 0, "VIDEO", "AE.ADBE Motion", "Position")
    kfs = (r.get("response") or {}).get("keyframes") or []
    print("position keyframes:", [(k.get("timeSeconds"), k.get("value")) for k in kfs])

    show("animate_clip_property (rotation 0->10)",
         m.animate_clip_property(seq, 0, 0, "rotation", [
             {"timeSeconds": 0.0, "value": 0},
             {"timeSeconds": 8.0, "value": 10},
         ]))


def stage_lumetri():
    seq = get_named_seq_id(STEREO_SEQ)

    show("add_lumetri_basic (calibration run)",
         m.add_lumetri_basic(seq, 0, 0, exposure=0.5, contrast=10,
                             temperature=25, saturation=120))

    show("get_lumetri_settings", m.get_lumetri_settings(seq, 0, 0))

    show("add_lumetri_creative", m.add_lumetri_creative(seq, 0, 0, vibrance=20))

    show("add_vignette", m.add_vignette(seq, 0, 0, amount=-2.0))


def stage_markers():
    seq = get_seq_id()  # phase1_test

    show("add_marker_to_sequence (Chapter at 5s)",
         m.add_marker_to_sequence(seq, "chapter 1", 5 * 254016000000,
                                  254016000000, "first chapter", "Chapter"))

    r = show("get_sequence_markers", m.get_sequence_markers(seq))
    markers = (r.get("response") or {}).get("markers") or []
    print("marker count:", len(markers))

    if markers:
        idx = len(markers) - 1
        show("update_marker (rename + move to 6s + color 3)",
             m.update_marker(seq, idx, name="chapter one",
                             start_time_seconds=6.0, color_index=3))
        r = m.get_sequence_markers(seq)
        mk = (r.get("response") or {}).get("markers", [])[idx]
        print("verify update:", mk.get("name"), mk.get("startSeconds"), mk.get("colorIndex"), mk.get("type"))

        show("remove_marker", m.remove_marker(seq, idx))
        r = m.get_sequence_markers(seq)
        print("count after remove:", len((r.get("response") or {}).get("markers") or []))

    show("add_clip_marker (clipA.mp4 at 2s)",
         m.add_clip_marker("clipA.mp4", "src note", 2.0, 0.5, "note on source"))

    show("get_media_info (clipA.mp4)", m.get_media_info("clipA.mp4"))

    show("set_clip_label_color (clipA.mp4 -> MANGO)",
         m.set_clip_label_color("clipA.mp4", color_name="MANGO"))

    show("get_project_item_metadata (clipA.mp4)",
         m.get_project_item_metadata("clipA.mp4"))

    show("batch_rename (prefix x_ on clipB)",
         m.batch_rename_project_items(item_names=["clipB.mp4"], prefix="x_"))
    show("batch_rename (undo: strip x_)",
         m.batch_rename_project_items(item_names=["x_clipB.mp4"], find="x_", replace=""))


def stage_transcripts():
    seq = get_named_seq_id(STEREO_SEQ)

    try:
        show("get_sequence_transcript (expect none/unavailable)",
             m.get_sequence_transcript(sequence_id=seq))
    except Exception as e:
        print("get_sequence_transcript ->", str(e)[:250])

    try:
        show("get_captions", m.get_captions(seq))
    except Exception as e:
        print("get_captions ->", str(e)[:250])

    show("save_project", m.save_project())


# ---------------------------------------------------------------------------
# Phase 3 stages
# ---------------------------------------------------------------------------

def stage_pipeline():
    r = show("get_sequence_list", m.get_sequence_list())

    r = show("create_empty_sequence", m.create_empty_sequence("p3_empty"))
    empty_id = (r.get("response") or {}).get("id")

    src = get_named_seq_id(STEREO_SEQ)
    r = show("duplicate_sequence (stereo_test -> p3_dup)",
             m.duplicate_sequence(src, "p3_dup"))

    show("open_in_source_monitor (clipA.mp4)",
         m.open_in_source_monitor(item_name="clipA.mp4"))

    # three-point edit: mark 2..4s of clipA, overwrite into the empty sequence
    show("set_source_in_out (clipA 2-4s)", m.set_source_in_out("clipA.mp4", 2.0, 4.0))
    show("overwrite marked range at 0s", m.overwrite_clip_at_time(empty_id, "clipA.mp4", 0.0, 0, 0))
    r = m.get_sequence_details(empty_id, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0), {})
    clips = [(c["startSeconds"], c["endSeconds"], c["inPointSeconds"]) for c in v0.get("clips", [])]
    print("three-point result (expect ~[(0, 2, 2)]):", clips)
    show("clear source in/out", m.set_source_in_out("clipA.mp4", clear=True))

    try:
        show("nest_clips (expect feature-detect)", m.nest_clips(src))
    except Exception as e:
        print("nest_clips ->", str(e)[:200])

    r = show("list_mogrt_library (installed path)", m.list_mogrt_library())

    r = m.list_export_presets()
    print("\n=== list_export_presets ===")
    print("preset count:", r.get("count"))
    for p in (r.get("presets") or [])[:5]:
        print(" ", p)

    presets = r.get("presets") or []
    if presets:
        try:
            r2 = show("get_export_file_extension (first preset)",
                      m.get_export_file_extension(src, presets[0]))
        except Exception as e:
            print("get_export_file_extension ->", str(e)[:200])

    for fn, name in [(m.export_aaf, "export_aaf"), (m.export_fcpxml, "export_fcpxml"),
                     (m.export_otio, "export_otio")]:
        try:
            show(name + " (expect feature-detect)", fn("F:\\premier\\media\\interchange_test.tmp", src))
        except Exception as e:
            print(f"{name} ->", str(e)[:160])


def stage_orchestration():
    import time as _time
    seq_name = f"p3_asm_{int(_time.time()) % 100000}"

    # 1. assemble a full edit from one JSON plan
    plan = {
        "newSequenceName": seq_name,
        "clips": [
            {"itemName": "clipA.mp4", "timeSeconds": 0.0, "mode": "overwrite"},
            {"itemName": "clipB.mp4", "timeSeconds": 10.0, "mode": "overwrite"},
        ],
        "transitions": [
            {"videoTrackIndex": 0, "trackItemIndex": 0,
             "name": "AE.ADBE Cross Dissolve New", "durationSeconds": 1.0,
             "clipAlignment": 0.5},
        ],
        "effects": [
            {"videoTrackIndex": 0, "trackItemIndex": 1,
             "matchName": "AE.ADBE Black & White", "properties": []},
        ],
        "lumetri": [
            {"videoTrackIndex": 0, "trackItemIndex": 0,
             "params": [{"name": "Temperature", "value": 20}]},
        ],
        "audio": [
            {"audioTrackIndex": 0, "trackItemIndex": 0, "volumeDb": -3.0,
             "fadeInSeconds": 1.0},
        ],
        "markers": [
            {"name": "cut here", "startTimeSeconds": 5.0, "durationSeconds": 0,
             "comments": "auto-cut test", "markerType": "Comment"},
            {"name": "cut here", "startTimeSeconds": 15.0, "durationSeconds": 0,
             "comments": "auto-cut test", "markerType": "Comment"},
        ],
    }
    r = show("assemble_timeline_from_plan", m.assemble_timeline_from_plan(plan))
    seq = (r.get("sequenceId") if isinstance(r, dict) else None)
    print("assembled sequence:", seq_name, seq)

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0), {})
    print("V1 after assembly:", [(c["name"], c["startSeconds"], c["endSeconds"]) for c in v0.get("clips", [])])

    # 2. auto-cut at the plan's markers -> exercises the SAFE split path
    #    (clips are adjacent at 10s... markers at 5 and 15 are inside clips)
    r = show("auto_cut_at_markers", m.auto_cut_at_markers(seq, 0, "VIDEO"))

    r = m.get_sequence_details(seq, include_effects=False)
    tracks = (r.get("response") or {}).get("tracks") or []
    v0 = next((t for t in tracks if t["trackType"] == "VIDEO" and t["trackIndex"] == 0), {})
    clips = [(c["startSeconds"], c["endSeconds"], c["inPointSeconds"]) for c in v0.get("clips", [])]
    print("V1 after auto-cut (expect 4 pieces 0-5-10-15-20):", clips)

    # 3. action sequence: save a look and play it on two clips
    show("create_action_sequence (warm_look)",
         m.create_action_sequence("warm_look", [
             {"operation": "lumetri",
              "settings": {"params": [{"name": "Temperature", "value": 30}]}},
             {"operation": "fade_video_in", "settings": {"durationSeconds": 0.5}},
         ], "warm grade + fade in"))

    show("play_action_sequence (2 clips)",
         m.play_action_sequence("warm_look", seq, [
             {"trackIndex": 0, "trackItemIndex": 0, "trackType": "VIDEO"},
             {"trackIndex": 0, "trackItemIndex": 2, "trackType": "VIDEO"},
         ]))

    show("list_action_sequences", m.list_action_sequences())

    show("save_project", m.save_project())


STAGES = {
    "smoke": stage_smoke,
    "build": stage_build,
    "effects": stage_effects,
    "timeline": stage_timeline,
    "audio": stage_audio,
    "retest": stage_retest,
    "keyframes": stage_keyframes,
    "lumetri": stage_lumetri,
    "markers": stage_markers,
    "transcripts": stage_transcripts,
    "pipeline": stage_pipeline,
    "orchestration": stage_orchestration,
}

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    STAGES[stage]()
