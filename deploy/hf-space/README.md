---
title: GramVarsha API
emoji: 🌧️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
short_description: Block-to-panchayat weather downscaling API (SIH26074)
---

# GramVarsha API

FastAPI backend for GramVarsha AI (SIH26074, Team Hexadecimal, WCE Sangli).
Downscales the block-level forecast to every gram panchayat in Miraj taluka with
kriging + XGBoost, explains it with SHAP, and serves crop advisories in English,
Hindi and Marathi.

- Health: `/api/health`
- Docs: `/docs`

Source and full README: see the project repository.
