datapulse/
├── .env                         ← YOU CREATE: copy from .env.example, add OPENAI_API_KEY
├── .env.example                 ← template for the above
├── docker-compose.yml
├── deploy_aws.sh
│
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── agent/
│       ├── __init__.py
│       ├── graph.py
│       ├── state.py
│       └── tools/
│           ├── __init__.py
│           ├── schema_inspector.py
│           ├── outlier_detector.py
│           ├── distribution_profiler.py
│           ├── duplicate_checker.py
│           └── correlation_mapper.py
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js           ← Vite boilerplate, keep
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── nginx-frontend.conf      ← used by frontend Dockerfile
│   ├── Dockerfile
│   ├── .env                     ← YOU CREATE for local dev: VITE_API_URL=http://localhost:8000
│   ├── .env.example             ← template for the above
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       └── components/
│           ├── FileDropzone.jsx
│           ├── ProgressStream.jsx
│           ├── QualityScore.jsx
│           └── ReportPanel.jsx
│
└── nginx/
    └── nginx.conf               ← EC2 host-level reverse proxy