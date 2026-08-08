"""
Package: evals.dashboard
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: Dev-facing FastAPI dashboard for exploring eval run artifacts locally.
Public surface: make_app — factory returning a configured FastAPI application.
              detail — run-detail rendering helpers (flaky table, calibration badge).
"""
