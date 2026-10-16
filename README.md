# EcoTwin — Smart Waste Management Frontend

A responsive, hackathon-ready frontend prototype for the problem statement:
**Smart Waste Management Digital Twin**.

## Run it
1. Extract `EcoTwin_Frontend.zip`.
2. Open the `smart_waste_twin_frontend` folder in VS Code.
3. Open `index.html` in a browser. Easiest option: install the VS Code extension **Live Server**, right-click `index.html`, then choose **Open with Live Server**.
4. Internet is needed for Google Fonts and Chart.js CDN. The rest of the interface is plain HTML, CSS and JavaScript.

## What's included
- Overview dashboard with sample metrics and waste stream chart
- AI Waste Scanner image upload and simulated classification result
- Digital Twin explorer with illustrative bin/zone map
- GenAI Insights page with preset example recommendations
- Collection Routes page
- System integration checklist
- Responsive layout for laptop and mobile

## Important demo note
This is a **frontend prototype**. Metrics are sample data; the waste classifier uses a random demo category; the GenAI advisor uses preset responses; the map is illustrative and not a live GIS/digital twin. Be transparent about this during judging.

## How to connect the team's backend later
Agree on API endpoints and response formats with your teammates. Example contracts:

### POST `/api/classify`
Request: multipart image file
Response:
```json
{
  "label": "plastic",
  "confidence": 0.94,
  "bin": "dry_recyclables",
  "guidance": "Empty and rinse if locally accepted."
}
```

### GET `/api/twin/summary`
Response:
```json
{
  "waste_today_tons": 12.8,
  "segregation_accuracy": 91.6,
  "bins_needing_pickup": 18,
  "collection_efficiency": 84.3
}
```

### POST `/api/insights`
Request:
```json
{
  "question": "How can we reduce overflow in Zone 1?",
  "metrics": {
    "high_fill_bins": 6,
    "segregation_accuracy": 91.6
  }
}
```
Response:
```json
{
  "recommendation": "Prioritise bins above 80% capacity...",
  "priority": "high"
}
```

### Frontend integration checklist
- Replace random classification in `index.html` with `fetch('/api/classify', ...)`.
- Replace preset GenAI answers with a call to your backend `/api/insights`.
- Replace sample metrics and illustrative map with `/api/twin/summary` and actual zone/bin records.
- Keep model/API keys on the backend. Never place private API keys in frontend JavaScript.
- Label recommendations as suggestions and validate them before operational use.

## Suggested presentation line
“EcoTwin is the operations dashboard: computer vision identifies waste, the digital twin represents bins and collection zones, and GenAI turns those signals into practical segregation and pickup recommendations.”
