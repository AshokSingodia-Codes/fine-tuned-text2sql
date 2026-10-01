"""Locust load test script for performance benchmarking."""

import random
from locust import HttpUser, between, task


class Text2SQLUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def validate_sql(self):
        sample_sqls = [
            "SELECT name FROM singer;",
            "SELECT count(*) FROM concert;",
            "DROP TABLE courses;",
            "SELECT * FROM users WHERE password='x';",
        ]
        sql = random.choice(sample_sqls)
        self.client.post("/v1/sql/validate", json={"sql": sql})

    @task(1)
    def query_text2sql(self):
        payload = {
            "db_id": "concert_singer",
            "question": "How many singers are there?",
        }
        self.client.post("/v1/query", json=payload)
