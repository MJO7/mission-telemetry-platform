// Real k6 load test against the live in-cluster api-service Service --
// not a synthetic "prove the YAML parses" check. Run as a k8s Job
// (see k8s/README.md) so it hits the Service's real ClusterIP/DNS the
// same way any in-cluster caller would, driving CPU load across
// whichever pods the HPA has scaled to at any given moment.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://api-service:8000";
const TOKEN = __ENV.TOKEN;

export const options = {
  scenarios: {
    ramping: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 80 },
        { duration: "3m", target: 80 },
        { duration: "30s", target: 0 },
      ],
    },
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/v1/auth/me`, {
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  check(res, { "status is 200": (r) => r.status === 200 });
  sleep(0.05);
}
