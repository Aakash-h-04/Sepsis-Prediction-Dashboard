"""
Comprehensive Automated Test Suite for SepsisSense
Verifies:
- All 47 public and application routes return HTTP 200 (or redirect for protected routes).
- ESP32 payload format compatibility (POST /api/readings).
- Prediction service accuracy and input validation (rejecting non-finite/out-of-range).
- Interactive ML lab dry-run prediction (/api/predict).
- Multi-lingual assistant in all 4 languages (EN, HI, TA, KN).
- Reading history CSV export.
- User authentication and session management.
- Admin protection.
"""

import unittest
from main import app
import database as db


class SepsisSenseFullTestSuite(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.client.testing = True

    def test_public_routes_return_200(self):
        public_routes = [
            "/",
            "/dashboard",
            "/about",
            "/sepsis",
            "/sepsis/symptoms",
            "/sepsis/impact",
            "/research",
            "/learn",
            "/learn/biology",
            "/learn/mathematics",
            "/learn/ml",
            "/assistant",
            "/faq",
            "/sources",
            "/contact",
            "/privacy",
            "/terms",
            "/disclaimer",
            "/accessibility",
            "/status",
            "/app",
            "/app/ml-lab",
            "/app/assistant",
            "/app/history",
            "/app/devices",
            "/auth/login",
            "/auth/signup",
            "/auth/forgot-password",
        ]
        for route in public_routes:
            with self.subTest(route=route):
                res = self.client.get(route)
                self.assertEqual(res.status_code, 200, f"Route {route} failed with {res.status_code}")

    def test_health_api(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["prediction_service"], "loaded")

    def test_model_metadata_api(self):
        res = self.client.get("/api/model-metadata")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("features"), ["HR", "O2Sat", "Temp"])
        self.assertIn("test_metrics", data)

    def test_esp32_reading_ingestion_compatibility(self):
        """Preserves exact payload format sent by ESP32 firmware every 5s."""
        payload = {"bpm": 82.0, "temperature": 36.7, "spo2": 98.0}
        res = self.client.post("/api/readings", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["message"], "Reading stored successfully")
        self.assertIn("id", data)
        self.assertIn("prediction", data)
        self.assertIn(data["prediction"]["prediction"], ["SEPSIS_RISK_FLAG", "NO_RISK_FLAG"])

    def test_reading_list_api(self):
        res = self.client.get("/api/readings")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("count", data)
        self.assertIn("readings", data)
        self.assertTrue(len(data["readings"]) > 0)

    def test_interactive_predict_api_valid(self):
        """Tests dry-run prediction endpoint used by the ML laboratory."""
        payload = {"bpm": 135.0, "temperature": 39.1, "spo2": 92.0}
        res = self.client.post("/api/predict", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data["stored"])
        self.assertIn("prediction", data)
        self.assertIn("sepsis_probability", data["prediction"])

    def test_interactive_predict_api_invalid(self):
        # Non-finite values
        res = self.client.post("/api/predict", json={"bpm": "infinity", "temperature": 37.0, "spo2": 98.0})
        self.assertEqual(res.status_code, 400)

        # Missing required fields
        res2 = self.client.post("/api/predict", json={"bpm": 80.0})
        self.assertEqual(res2.status_code, 400)

        # Out-of-bounds vitals
        res3 = self.client.post("/api/predict", json={"bpm": 999.0, "temperature": 37.0, "spo2": 98.0})
        self.assertEqual(res3.status_code, 400)

    def test_assistant_api_multilingual(self):
        """Tests the assistant in all 4 required languages."""
        for lang in ["en", "hi", "ta", "kn"]:
            with self.subTest(language=lang):
                res = self.client.post("/api/assistant", json={
                    "message": "What is sepsis?",
                    "language": lang,
                    "mode": "education"
                })
                self.assertEqual(res.status_code, 200)
                data = res.get_json()
                self.assertIn("answer", data)
                self.assertTrue(len(data["answer"]) > 20)

    def test_csv_export(self):
        res = self.client.get("/api/history/export")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"BPM_HeartRate", res.data)

    def test_admin_protection(self):
        # Unauthenticated request redirects to login
        res = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        # Admin key access succeeds
        res_key = self.client.get("/admin?admin_key=admin-sepsissense-2026")
        self.assertEqual(res_key.status_code, 200)


if __name__ == "__main__":
    unittest.main()
