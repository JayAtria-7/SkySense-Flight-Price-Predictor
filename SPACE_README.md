---
title: FlightIQ
emoji: ✈️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
---

# FlightIQ - AI Flight Price Predictor

AI-powered flight price prediction system built with FastAPI and scikit-learn.

## Features

- 🎯 Accurate price predictions using Random Forest Regressor
- 📊 Smart imputation with route-based medians
- 🔍 Transparent assumptions and uncertainty estimates
- 💡 Top contributing factors for each prediction
- 🎨 Clean, accessible web interface

## How it works

The model trains on historical flight data and predicts prices based on:
- Route (source & destination cities)
- Travel class (Economy/Business)
- Number of stops
- Days before departure
- Flight duration
- Airline, departure/arrival times (optional)

## Dataset

The model loads training data from the GitHub repository or a custom `DATASET_URL` environment variable.

## Environment Variables

- `DATASET_URL` (optional): URL to your CSV dataset
- `MAX_TRAIN_ROWS` (optional): Limit training dataset size (default: 25000)

## API Endpoints

- `GET /` - Redirects to the web UI
- `GET /ui/` - Interactive web interface
- `GET /api/health` - Health check and model version
- `GET /api/metadata` - Allowed values and defaults
- `POST /api/predict` - Make a price prediction

## Credits

**FlightIQ** made by [Jay Prakash Kumar](https://www.linkedin.com/in/jay-prakash-kumar-1b534a260)

- GitHub: [JayAtria-7](https://github.com/JayAtria-7)
- LeetCode: [JayAtria_7](https://leetcode.com/u/JayAtria_7/)
- Email: jay.prakash7.kr@gmail.com

© 2025 FlightIQ. All rights reserved.
