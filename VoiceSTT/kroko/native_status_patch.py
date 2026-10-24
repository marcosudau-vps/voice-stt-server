"""Versioned local extension of the pinned native client, never a network client."""


def patch_native_license_status(repo_dir):
    """Apply fail-closed V1 snapshot instrumentation to the declared upstream pin.

    All replacements require exactly one known anchor; source drift is fatal.
    The native singleton stays in the serving owner. No separate activation API.
    """
    from pathlib import Path
    import hashlib

    originals = {
        "sherpa-onnx/csrc/license.h": "68f23b22e449e14fdc6c82cecdf640a9ab18b88bca422c192e0fca5e5172458c",
        "sherpa-onnx/csrc/online-transducer-model.cc": "a697cc9048dcc361da5c85de342a63c903eea7b3d464044c6cbd74c6f3731040",
        "sherpa-onnx/python/csrc/sherpa-onnx.cc": "071b4ae2a917f3479f57966726744a2425cdc56408b2a467d90aadb82bc39f80",
    }
    for relative, digest in originals.items():
        text = (Path(repo_dir) / relative).read_text(encoding="utf-8")
        if "VOICESTT_LICENSE_STATUS_V1" not in text and hashlib.sha256(text.encode("utf-8")).hexdigest() != digest:
            raise RuntimeError("native status patch requires declared source: " + relative)

    def edit(relative, changes):
        path = Path(repo_dir) / relative
        text = path.read_text(encoding="utf-8")
        if "VOICESTT_LICENSE_STATUS_V1" in text:
            return
        for old, new in changes:
            if text.count(old) != 1:
                raise RuntimeError("native status patch anchor mismatch: " + relative)
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8", newline="\n")

    status_members = r'''// VOICESTT_LICENSE_STATUS_V1
    mutable std::recursive_mutex status_mutex;
    std::string status_model_id;
    std::string status_outcome = "unreachable";
    std::chrono::steady_clock::time_point status_confirmed;
    double status_ttl = 0;
    bool status_initialized = false;

    void status_fail() {
        std::lock_guard<std::recursive_mutex> guard(status_mutex);
        status_outcome = "unreachable";
        status_ttl = 0;
        status_initialized = false;
    }

    void status_response(const json& j, bool usage) {
        std::lock_guard<std::recursive_mutex> guard(status_mutex);
        // A successful transport/open is never proof. Only fully parsed
        // positive replies for the singleton's exact model may grant.
        if (!j.contains("allowed") || !j.at("allowed").is_boolean()) {
            status_fail(); return;
        }
        if (!j.at("allowed").get<bool>()) {
            status_outcome = "rejected"; status_ttl = 0; status_initialized = false; return;
        }
        if (!j.contains("remaining_seconds") ||
            !j.at("remaining_seconds").is_number_integer()) {
            status_fail(); return;
        }
        if (j.contains("error") && (!j.at("error").is_string() ||
            (j.at("error").get<std::string>() != "" && j.at("error").get<std::string>() != "no"))) {
            status_fail(); return;
        }
        if (!usage) {
            if (!j.contains("offline_timeout") ||
                !j.at("offline_timeout").is_number_integer() ||
                !j.contains("report_interval") ||
                !j.at("report_interval").is_number_integer() ||
                !j.contains("expirable") || !j.at("expirable").is_boolean() ||
                j.at("expirable").get<bool>() || password.empty()) {
                // Expirable replies lack a qualified portable date contract.
                status_fail(); return;
            }
            status_initialized = true;
        }
        if (!status_initialized || offline_timeout.load() <= 0 ||
            report_interval.load() <= 0 || remaining_seconds.load() <= 0 ||
            status_model_id.empty()) {
            status_fail(); return;
        }
        status_ttl = std::min(60.0, std::min(
            double(offline_timeout.load()), double(remaining_seconds.load())));
        status_confirmed = std::chrono::steady_clock::now();
        status_outcome = "granted";
    }

    std::string status_json() const {
        std::lock_guard<std::recursive_mutex> guard(status_mutex);
        double age = status_outcome == "granted" ?
            std::chrono::duration<double>(std::chrono::steady_clock::now() -
                                         status_confirmed).count() : 0;
        const char* owner = std::getenv("VOICESTT_KROKO_OWNER_GENERATION");
        return json{{"schemaVersion", 1}, {"modelId", status_model_id},
                    {"outcome", status_outcome}, {"proofAgeSeconds", age},
                    {"maxProofAgeSeconds", status_ttl},
                    {"ownerGeneration", owner ? owner : ""}}.dump();
    }

    std::string activation_password() const {
        std::lock_guard<std::recursive_mutex> guard(status_mutex);
        return password;
    }

    std::string safe_error() const { return "native_license_failure"; }
'''
    edit("sherpa-onnx/csrc/license.h", [
        ("#include <regex>", "#include <regex>\n#include <mutex>\n#include <atomic>\n#include <algorithm>\n#include <cstdlib>"),
        ("    wsclient c;", "    wsclient c;\n" + status_members),
        ("    bool allowed = false;", "    std::atomic<bool> allowed{false};"),
        ("    int remaining_seconds = 0;", "    std::atomic<int> remaining_seconds{0};"),
        ("    int offline_timeout = 0;", "    std::atomic<int> offline_timeout{0};"),
        ("    int report_interval = 0;", "    std::atomic<int> report_interval{0};"),
        ("    bool is_finish = false;", "    std::atomic<bool> is_finish{false};"),
        ("    bool is_connected = false;", "    std::atomic<bool> is_connected{false};"),
    ])
    # Remaining edits use a separate transaction marker for idempotent replay.
    path = Path(repo_dir) / "sherpa-onnx/csrc/license.h"
    text = path.read_text(encoding="utf-8")
    if "VOICESTT_STATUS_CALLBACKS_V1" not in text:
        text = text.replace("            hdl = hdl_in; // store for later use", "            // VOICESTT_STATUS_CALLBACKS_V1\n            std::lock_guard<std::recursive_mutex> guard(status_mutex);\n            hdl = hdl_in; // store for later use")
        text = text.replace('                        is_finish = true;\n                        return;', '                        status_response(j, false);\n                        is_finish = true;\n                        return;')
        text = text.replace('                    is_finish = true;\n                    return;', '                    status_response(j, false);\n                    is_finish = true;\n                    return;')
        text = text.replace('                        error_message = err;', '                        status_fail();\n                        error_message = err;')
        text = text.replace('j.value("remaining_seconds", remaining_seconds)', 'j.value("remaining_seconds", remaining_seconds.load())')
        text = text.replace('                    std::cout << "⏱️', '                    status_response(j, true);\n                    std::cout << "⏱️')
        text = text.replace('                }\n\n            } catch', '                }\n                else { status_fail(); }\n\n            } catch')
        text = text.replace('            } catch (const std::exception& e) {', '            } catch (const std::exception& e) {\n                status_fail();')
        text = text.replace('            hdl = hdl_in;\n            is_connected = true;', '            std::lock_guard<std::recursive_mutex> guard(status_mutex);\n            status_fail();\n            hdl = hdl_in;\n            is_connected = true;')
        text = text.replace('            is_connected = false;', '            std::lock_guard<std::recursive_mutex> guard(status_mutex);\n            status_fail();\n            is_connected = false;')
        text = text.replace('        last_online_time = std::chrono::steady_clock::now();\n\n        while (true)', '        {\n            std::lock_guard<std::recursive_mutex> guard(status_mutex);\n            status_model_id = modelIdReq;\n            last_online_time = std::chrono::steady_clock::now();\n        }\n\n        while (true)')
        text = text.replace('        if (!hdl.lock()) {', '        if (!hdl.lock()) {\n            status_fail();')
        text = text.replace('        if (ec) {', '        if (ec) {\n            status_fail();')
        text = text.replace('    bool send_usage_report(int seconds_used) {', '    bool send_usage_report(int seconds_used) {\n        std::lock_guard<std::recursive_mutex> guard(status_mutex);')
        text = text.replace('    void check_offline_timeout() {', '    void check_offline_timeout() {\n        std::lock_guard<std::recursive_mutex> guard(status_mutex);')
        # Never allow native output to expose provider raw errors or URI credentials.
        text = text.replace('<< error_message', '<< "native_license_failure"').replace('<< err <<', '<< "native_license_failure" <<').replace('<< e.what()', '<< "native_license_failure"').replace('<< ec.message()', '<< "native_license_failure"').replace('<< client.error_message', '<< client.safe_error()')
        path.write_text(text, encoding="utf-8", newline="\n")

    edit("sherpa-onnx/csrc/online-transducer-model.cc", [
        ('namespace sherpa_onnx {', r'''namespace sherpa_onnx {
// VOICESTT_LICENSE_STATUS_V1
std::string KrokoLicenseStatusV1() {
#ifdef KROKO_LICENSE
  return LicenseState::getInstance().status_json();
#else
  return "{\"schemaVersion\":1,\"outcome\":\"unreachable\"}";
#endif
}
'''),
        ('client.report_interval > 0 ? client.report_interval : 60', 'client.report_interval.load() > 0 ? client.report_interval.load() : 60'),
        ('duration = client.remaining_seconds;', 'duration = client.remaining_seconds.load();'),
        ('<< client.error_message', '<< client.safe_error()'),
        ('model.decryptPayload(client.password)', 'model.decryptPayload(client.activation_password())'),
    ])
    edit("sherpa-onnx/python/csrc/sherpa-onnx.cc", [
        ('namespace sherpa_onnx {', 'namespace sherpa_onnx {\n// VOICESTT_LICENSE_STATUS_V1\nstd::string KrokoLicenseStatusV1();'),
        ('  m.doc() = "pybind11 binding of sherpa-onnx";', '  m.doc() = "pybind11 binding of sherpa-onnx";\n  m.def("voicestt_license_status_v1", &KrokoLicenseStatusV1);'),
    ])
