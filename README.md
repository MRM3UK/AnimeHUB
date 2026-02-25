# 🎌 Anime Streaming Website

Modern anime streaming platform built with Flask and vanilla JavaScript.

## 🚀 Features

- Search anime by keyword
- Browse latest updates and trending anime
- Watch episodes with multiple servers
- Responsive design for mobile and desktop
- Fast API with caching

## 🛠️ Tech Stack

**Backend:**
- Flask (Python)
- BeautifulSoup4 for web scraping
- Requests for HTTP calls

**Frontend:**
- Vanilla JavaScript
- HTML5 & CSS3
- Responsive design

## 📦 Deployment

Deployed on Vercel: [Your URL will be here]

## 🔗 API Endpoints

- `GET /api/home` - Home page data
- `GET /api/search?keyword=naruto` - Search anime
- `GET /api/anime/:slug` - Anime details
- `GET /api/episodes/:ani_id` - Episode list
- `GET /api/servers/:ep_token` - Available servers
- `GET /api/source/:link_id` - Video source

## 📄 License

MIT License
