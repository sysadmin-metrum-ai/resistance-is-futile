# Drone Swarm Dashboard

Web dashboard for the Drone Swarm Agent Integration system.

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your API URL and key
   ```

3. **Run development server:**
   ```bash
   npm run dev
   ```

4. **Open dashboard:**
   Navigate to [http://localhost:3000](http://localhost:3000)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (default: http://localhost:8000) |
| `NEXT_PUBLIC_API_KEY` | API key for authentication |

## Project Structure

```
src/
├── app/              # Next.js app router pages
├── components/       # React components
│   ├── ui/          # shadcn/ui components
│   └── DashboardLayout.tsx
├── lib/             # Utilities and API client
│   └── api.ts       # Typed API functions
└── types/           # TypeScript type definitions
    └── index.ts     # Mirror of backend types
```

## Customization

- **Logo:** Place your logo at `public/logos/logo.png` or `public/logos/logo.svg`
- **Theme:** Colors are configured in `src/app/globals.css` via CSS variables
