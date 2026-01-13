# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Initialize Database

```bash
python scripts/init_db.py
```

### 2. Start Backend API

```bash
research serve --port 8002 --reload
```

### 3. Start Reflex Frontend (new terminal)

```bash
cd reflex_app
reflex run
```

### 4. Open Browser

Visit: **http://localhost:3000**

### 5. Create Account

1. Click "Register"
2. Enter username, email, password
3. First user becomes admin!

---

## 📋 What You Built

✅ **Multi-user place research app**

- Each user has their own saved places
- Customizable preferences per user
- Compare places side-by-side

✅ **User Preferences**

- Custom distance addresses (e.g., "Mom's house")
- Toggle providers on/off
- Set minimum thresholds (walk score, etc.)

✅ **Pages**

- `/login` - Authentication
- `/enrich` - Enrich addresses
- `/places` - Your saved places
- `/compare` - Compare places
- `/preferences` - Configure settings

---

## 🔧 Configuration

### Required API Keys (.env)

```env
JWT_SECRET_KEY=your-secret-key
GOOGLE_MAPS_API_KEY=your-key  # For geocoding
```

### Optional API Keys

```env
WALKSCORE_API_KEY=your-key
AIRNOW_API_KEY=your-key
NATIONAL_FLOOD_DATA_API_KEY=your-key
```

---

## 📖 Usage Flow

1. **Register** → Create your account
2. **Preferences** → Set your custom addresses & thresholds
3. **Enrich** → Enter an address, get all the data
4. **Save** → Add it to your collection
5. **Compare** → Select 2+ places to compare

---

## 🐛 Troubleshooting

**Can't login?**

- Check API is running on port 8002
- Check `rxconfig.py` has correct `api_url`

**No providers working?**

- Add API keys to `.env`
- Restart the backend API
- Check http://localhost:8002/providers

**Database error?**

- Run `python scripts/init_db.py`

---

## 📚 Documentation

- Full details: [REFLEX_IMPLEMENTATION.md](REFLEX_IMPLEMENTATION.md)
- Frontend docs: [reflex_app/README.md](reflex_app/README.md)
- API docs: http://localhost:8002/docs

---

## 🎯 Next Steps

1. Configure your preferences (custom addresses)
2. Enrich a few addresses
3. Compare them side-by-side
4. Find your perfect place to live!

---

Happy house hunting! 🏡
