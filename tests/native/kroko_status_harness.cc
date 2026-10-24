// Local C++ status qualification with synthetic replies. No sockets are opened.
#include "sherpa-onnx/csrc/license.h"
#include <cassert>
#include <thread>

int main() {
  LicenseClient client;
  client.status_model_id = "synthetic-model";
  client.remaining_seconds = 100;
  client.offline_timeout = 20;
  client.report_interval = 5;
  client.password = "synthetic-private-password";
  json positive = {{"allowed", true}, {"remaining_seconds", 100},
                   {"offline_timeout", 20}, {"report_interval", 5},
                   {"expirable", false}};
  client.status_response(positive, false);
  auto snapshot = json::parse(client.status_json());
  assert(snapshot["schemaVersion"] == 1);
  assert(snapshot["outcome"] == "granted");
  assert(snapshot["modelId"] == "synthetic-model");
  assert(snapshot["maxProofAgeSeconds"] == 20);
  assert(client.status_json().find("synthetic-private-password") == std::string::npos);
  assert(!snapshot.contains("password"));
  assert(!snapshot.contains("error"));
  client.status_response({{"allowed", false}}, false);
  assert(json::parse(client.status_json())["outcome"] == "rejected");
  client.status_response({{"allowed", true}}, false);
  assert(json::parse(client.status_json())["outcome"] == "unreachable");
  auto expirable = positive;
  expirable["expirable"] = true;
  client.status_response(expirable, false);
  assert(json::parse(client.status_json())["outcome"] == "unreachable");
  client.status_response(positive, false);
  auto first = json::parse(client.status_json())["proofAgeSeconds"].get<double>();
  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  assert(json::parse(client.status_json())["proofAgeSeconds"].get<double>() > first);
  std::thread writer([&] {
    for (int i = 0; i < 2000; ++i) {
      client.status_response(positive, false);
      client.status_response({{"allowed", false}}, false);
      client.status_fail();
    }
  });
  std::thread reader([&] {
    for (int i = 0; i < 2000; ++i) {
      auto data = json::parse(client.status_json());
      if (data["outcome"] == "granted") {
        assert(data["maxProofAgeSeconds"] == 20);
        assert(data["proofAgeSeconds"].get<double>() >= 0);
      } else {
        assert(data["maxProofAgeSeconds"] == 0);
      }
    }
  });
  writer.join(); reader.join();
  std::cout << "PASS native V1 synthetic snapshot and concurrent readers/writers\n";
}
