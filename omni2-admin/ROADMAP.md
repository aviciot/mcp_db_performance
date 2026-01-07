# Omni2 Admin Dashboard - Development Roadmap

**Version**: 1.0  
**Project Start**: January 6, 2026  
**Status**: 🚧 In Progress

---

## 📋 Project Overview

**Goal**: Build a modern, responsive admin dashboard for Omni2 MCP Hub with "wow factor" UI/UX

**Timeline**: 4-6 weeks (20-30 business days)  
**Team**: 1-2 developers  
**Methodology**: Agile, iterative development with weekly milestones

---

## 🎯 Milestones

### Phase 1: Foundation (Week 1)
**Goal**: Set up project infrastructure and core architecture  
**Duration**: 5 days  
**Status**: ✅ Complete

#### Tasks
- [x] Create design document (DESIGN.md)
- [x] Create architecture document (ARCHITECTURE.md)
- [x] Create roadmap (this document)
- [x] Initialize backend project structure
- [x] Initialize frontend project structure
- [x] Set up Docker Compose configuration
- [x] Design database schema (admin tables)
- [x] Create Alembic migrations
- [x] Set up development environment
- [x] Configure ESLint, Prettier, pre-commit hooks

**Deliverables**:
- ✅ Project documentation (DESIGN.md, ARCHITECTURE.md, ROADMAP.md)
- ✅ Backend scaffolding (FastAPI + SQLAlchemy)
- ✅ Frontend scaffolding (Next.js 14 + TypeScript)
- ✅ docker-compose.yml for all services
- ✅ Database migrations ready
- ✅ Development environment working

---

### Phase 2: Authentication & Authorization (Week 2)
**Goal**: Implement secure authentication system  
**Duration**: 5 days  
**Status**: ✅ Complete

#### Backend Tasks
- [x] Implement password hashing (bcrypt)
- [x] Create JWT token generation/validation
- [x] Build login endpoint (/api/v1/auth/login)
- [x] Build logout endpoint (/api/v1/auth/logout)
- [x] Build token refresh endpoint (/api/v1/auth/refresh)
- [x] Build "get current user" endpoint (/api/v1/auth/me)
- [x] Implement auth middleware
- [x] Implement role-based authorization
- [x] Add rate limiting (5 attempts/min for login)
- [x] Create seed script for admin user

#### Frontend Tasks
- [x] Build login page UI
- [x] Implement auth context/store (Zustand)
- [x] Build protected route wrapper
- [x] Implement token refresh logic
- [x] Add auth interceptor for API calls
- [x] Create logout functionality
- [x] Handle session expiry gracefully
- [x] Fix auth persistence (prevent logout on F5 refresh)

**Deliverables**:
- ✅ Secure authentication system
- ✅ JWT-based authorization
- ✅ Login/logout flow working
- ✅ Admin user seeded in database
- ✅ All auth tests passing
- ✅ Auth persists across page refreshes

---

### Phase 3: Dashboard Core (Week 2-3)
**Goal**: Build main dashboard with key metrics  
**Duration**: 5 days  
**Status**: ✅ Complete

#### Backend Tasks
- [x] Create dashboard stats endpoint (/api/v1/dashboard/stats)
- [x] Create activity feed endpoint (/api/v1/dashboard/activity)
- [x] Create chart data endpoint (/api/v1/dashboard/charts)
- [x] Optimize queries with indexes
- [x] Fix database models to match Omni2 schema
- [x] Re-enable cost tracking with cost_estimate column
- [x] Add caching for expensive queries (if needed)

#### Frontend Tasks
- [x] Build dashboard layout (sidebar + header)
- [x] Build hero stats cards (4 metrics)
- [x] Build activity feed component (real-time ready)
- [x] Build query/hour chart (Recharts)
- [x] Build cost by MCP chart (Recharts)
- [x] Build MCP health status grid
- [x] Implement dark/light theme toggle
- [x] Add loading skeletons
- [x] Make responsive (mobile/tablet/desktop)
- [x] Add animations (Framer Motion)

**Deliverables**:
- ✅ Dashboard showing live stats (4 MCPs, 11 users, 12 API calls)
- ✅ Charts visualizing data
- ✅ Beautiful, responsive UI
- ✅ Dark/light theme working
- ✅ Smooth animations
- ✅ Real activity feed with 10+ items
- ✅ Cost tracking functional

**Critical Fixes Applied**:
- Fixed User model: `username` → `name`, added 11 missing fields (slack_user_id, is_super_admin, etc.)
- Fixed AuditLog model: Added 20+ missing columns (cost_estimate, tokens_cached, databases_accessed, etc.)
- Re-enabled cost calculation using correct cost_estimate column
- Fixed auth store to prevent logout on page refresh

---

### Phase 4: MCP Management (Week 3)
**Goal**: Full CRUD for MCP servers  
**Duration**: 5 days  
**Status**: ⏳ Not Started

#### Backend Tasks
- [ ] Create MCP list endpoint (/api/v1/mcps)
- [ ] Create MCP detail endpoint (/api/v1/mcps/{id})
- [ ] Create MCP create endpoint (POST /api/v1/mcps)
- [ ] Create MCP update endpoint (PUT /api/v1/mcps/{id})
- [ ] Create MCP delete endpoint (DELETE /api/v1/mcps/{id})
- [ ] Create health check trigger endpoint (POST /api/v1/mcps/{id}/health)
- [ ] Create tools list endpoint (/api/v1/mcps/{id}/tools)
- [ ] Create MCP analytics endpoint (/api/v1/mcps/{id}/analytics)
- [ ] Implement enable/disable endpoints
- [ ] Add validation for MCP config (URL, port, etc.)
- [ ] Log all actions in admin_audit_logs

#### Frontend Tasks
- [ ] Build MCP list page (card grid)
- [ ] Build MCP detail modal/page
- [ ] Build MCP create form
- [ ] Build MCP edit form
- [ ] Add form validation (React Hook Form + Zod)
- [ ] Build health status indicator
- [ ] Build tools list component
- [ ] Add delete confirmation dialog
- [ ] Add enable/disable toggle
- [ ] Add search/filter functionality
- [ ] Add sorting options
- [ ] Make responsive

**Deliverables**:
- ✨ Full MCP management interface
- 📝 Create/Edit forms with validation
- 🔍 Search and filter working
- 🎯 Health checks triggerable
- 🗑️ Safe delete with confirmation

---

### Phase 5: User Management (Week 4)
**Goal**: Full CRUD for Omni2 users  
**Duration**: 4 days  
**Status**: ⏳ Not Started

#### Backend Tasks
- [ ] Create user list endpoint (/api/v1/users)
- [ ] Create user detail endpoint (/api/v1/users/{id})
- [ ] Create user create endpoint (POST /api/v1/users)
- [ ] Create user update endpoint (PUT /api/v1/users/{id})
- [ ] Create user delete endpoint (DELETE /api/v1/users/{id})
- [ ] Create user activity endpoint (/api/v1/users/{id}/activity)
- [ ] Create update permissions endpoint (PUT /api/v1/users/{id}/permissions)
- [ ] Implement enable/disable endpoints
- [ ] Add validation for user data
- [ ] Log all actions in admin_audit_logs

#### Frontend Tasks
- [ ] Build user list page (table view)
- [ ] Build user detail panel/page
- [ ] Build user create form
- [ ] Build user edit form
- [ ] Build permissions editor
- [ ] Build activity log viewer
- [ ] Add search/filter functionality
- [ ] Add role selector dropdown
- [ ] Add enable/disable toggle
- [ ] Make responsive

**Deliverables**:
- 👥 Full user management interface
- 📝 Create/Edit forms with validation
- 🔐 Permissions management
- 📜 Activity log viewing
- 🔍 Search and filter working

---

### Phase 6: Configuration Management (Week 4)
**Goal**: YAML ↔ PostgreSQL sync  
**Duration**: 3 days  
**Status**: ⏳ Not Started

#### Backend Tasks
- [ ] Create get source endpoint (/api/v1/config/source)
- [ ] Create import YAML endpoint (POST /api/v1/config/import)
- [ ] Create export to YAML endpoint (POST /api/v1/config/export)
- [ ] Create diff endpoint (/api/v1/config/diff)
- [ ] Create snapshots list endpoint (/api/v1/config/snapshots)
- [ ] Create rollback endpoint (POST /api/v1/config/rollback)
- [ ] Create get MCPs config endpoint (/api/v1/config/mcps)
- [ ] Create update MCPs config endpoint (PUT /api/v1/config/mcps)
- [ ] Implement YAML parser
- [ ] Implement config validator
- [ ] Create snapshot on every import/export

#### Frontend Tasks
- [ ] Build config management page
- [ ] Build source indicator (YAML vs DB)
- [ ] Build import button with file picker
- [ ] Build export button
- [ ] Build diff viewer (split view)
- [ ] Build snapshot list with dates
- [ ] Build rollback confirmation dialog
- [ ] Build inline config editor
- [ ] Add syntax highlighting (Monaco Editor)
- [ ] Make responsive

**Deliverables**:
- ⚙️ Config management interface
- 📂 Import/Export working
- 🔍 Diff viewer showing changes
- 💾 Snapshots for rollback
- ✏️ Inline editing with validation

---

### Phase 7: Analytics (Week 5)
**Goal**: Rich data visualization and insights  
**Duration**: 5 days  
**Status**: ⏳ Not Started

#### Backend Tasks
- [ ] Create analytics overview endpoint (/api/v1/analytics/overview)
- [ ] Create cost breakdown endpoint (/api/v1/analytics/cost)
- [ ] Create performance metrics endpoint (/api/v1/analytics/performance)
- [ ] Create error summary endpoint (/api/v1/analytics/errors)
- [ ] Create user activity endpoint (/api/v1/analytics/users)
- [ ] Create tool popularity endpoint (/api/v1/analytics/tools)
- [ ] Create trends endpoint (/api/v1/analytics/trends)
- [ ] Create export to CSV endpoint (POST /api/v1/analytics/export)
- [ ] Optimize queries for large datasets
- [ ] Add date range filtering
- [ ] Add aggregation options (day/week/month)

#### Frontend Tasks
- [ ] Build analytics page layout
- [ ] Build cost breakdown chart (pie/donut)
- [ ] Build cost over time chart (line/area)
- [ ] Build queries by MCP chart (bar)
- [ ] Build performance chart (scatter/line)
- [ ] Build error rate chart (line)
- [ ] Build user activity heatmap
- [ ] Build tool popularity chart (bar)
- [ ] Build date range picker
- [ ] Build metric cards (top MCPs, top users, etc.)
- [ ] Add export to CSV button
- [ ] Make responsive

**Deliverables**:
- 📊 Rich analytics dashboard
- 📈 Multiple chart types (line, bar, pie, area)
- 🗓️ Date range filtering
- 💰 Cost breakdown visualizations
- 📥 Export to CSV

---

### Phase 8: Real-Time Updates (Week 5-6)
**Goal**: Implement WebSocket for live updates  
**Duration**: 4 days  
**Status**: ⏳ Not Started

#### Backend Tasks
- [ ] Implement WebSocket endpoint (/ws)
- [ ] Set up PostgreSQL LISTEN/NOTIFY
- [ ] Create triggers for audit_logs table
- [ ] Create triggers for mcp_servers table
- [ ] Create triggers for users table
- [ ] Implement subscription management
- [ ] Implement channel broadcasting
- [ ] Add WebSocket authentication
- [ ] Handle connection lifecycle (connect/disconnect/reconnect)
- [ ] Add heartbeat/ping-pong

#### Frontend Tasks
- [ ] Implement WebSocket client
- [ ] Create WebSocket context/hook
- [ ] Implement auto-reconnect logic
- [ ] Subscribe to channels (dashboard, audit_logs, mcp:*)
- [ ] Handle incoming events
- [ ] Update activity feed in real-time
- [ ] Update stats in real-time
- [ ] Update MCP status in real-time
- [ ] Show connection status indicator
- [ ] Add toast notifications for important events

**Deliverables**:
- 🔴 Live updates working
- 📡 WebSocket connection stable
- 🔄 Auto-reconnect on disconnect
- 🔔 Real-time notifications
- ⚡ Activity feed updating instantly

---

### Phase 9: Polish & Enhancement (Week 6)
**Goal**: Final touches and "wow factor" features  
**Duration**: 5 days  
**Status**: ⏳ Not Started

#### UI/UX Tasks
- [ ] Add glassmorphism effects
- [ ] Add smooth page transitions
- [ ] Add skeleton loaders everywhere
- [ ] Add empty states with illustrations
- [ ] Add error states with retry buttons
- [ ] Implement command palette (Cmd+K)
- [ ] Add keyboard shortcuts
- [ ] Add tooltips for all icons/buttons
- [ ] Add breadcrumbs navigation
- [ ] Polish animations (stagger, fade, slide)
- [ ] Add loading bars (NProgress)
- [ ] Add confetti on success actions (optional)
- [ ] Optimize images and assets
- [ ] Add favicon and meta tags

#### Accessibility Tasks
- [ ] Audit with Lighthouse
- [ ] Fix all WCAG 2.1 AA issues
- [ ] Add ARIA labels
- [ ] Ensure keyboard navigation works
- [ ] Test with screen reader
- [ ] Add focus indicators
- [ ] Ensure color contrast ratios
- [ ] Add skip to content link

#### Performance Tasks
- [ ] Optimize bundle size
- [ ] Lazy load heavy components
- [ ] Implement virtual scrolling for large lists
- [ ] Add service worker (PWA - optional)
- [ ] Optimize database queries
- [ ] Add database indexes where needed
- [ ] Profile and fix bottlenecks

#### Testing Tasks
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests
- [ ] Write E2E tests (Playwright)
- [ ] Test on different browsers
- [ ] Test on mobile devices
- [ ] Test with different screen sizes
- [ ] Load testing (k6 or Locust)

**Deliverables**:
- ✨ Polished UI with wow factor
- ♿ WCAG 2.1 AA compliant
- 🚀 Optimized performance
- 🧪 >80% test coverage
- 📱 Works perfectly on mobile

---

### Phase 10: Documentation & Deployment (Week 6)
**Goal**: Complete documentation and deploy  
**Duration**: 2 days  
**Status**: ⏳ Not Started

#### Documentation Tasks
- [ ] Write README.md for project
- [ ] Write API documentation (OpenAPI/Swagger)
- [ ] Write deployment guide
- [ ] Write user guide (how to use dashboard)
- [ ] Write developer guide (how to extend)
- [ ] Document environment variables
- [ ] Create troubleshooting guide
- [ ] Add inline code comments
- [ ] Create video walkthrough (optional)

#### Deployment Tasks
- [ ] Set up production environment variables
- [ ] Configure production database
- [ ] Build Docker images
- [ ] Test Docker Compose in production mode
- [ ] Set up reverse proxy (Traefik/Nginx)
- [ ] Configure SSL certificates
- [ ] Set up monitoring (Prometheus/Grafana - optional)
- [ ] Set up logging aggregation (ELK - optional)
- [ ] Create backup strategy
- [ ] Deploy to staging
- [ ] Test in staging
- [ ] Deploy to production
- [ ] Smoke test production

**Deliverables**:
- 📚 Complete documentation
- 🚀 Production deployment
- 🔒 SSL configured
- 📊 Monitoring set up (optional)
- ✅ All systems operational

---

## 🎓 Learning Goals & Challenges

### Technical Challenges
1. **Real-time performance**: Efficiently broadcasting updates to multiple clients
2. **Complex analytics queries**: Optimizing PostgreSQL queries for large datasets
3. **Config sync**: Reliable bidirectional sync between YAML and PostgreSQL
4. **WebSocket resilience**: Handling reconnects, buffering messages, etc.
5. **Responsive design**: Making complex tables/charts work on mobile

### Skills to Develop
- FastAPI WebSocket implementation
- PostgreSQL LISTEN/NOTIFY mechanism
- Next.js 14 App Router patterns
- shadcn/ui component customization
- React Query advanced patterns
- Recharts data visualization
- Docker multi-stage builds

---

## 📊 Progress Tracking

### Overall Progress: 5% (3/60 tasks completed)

| Phase | Tasks | Completed | Progress |
|-------|-------|-----------|----------|
| Phase 1: Foundation | 10 | 3 | 30% ⏳ |
| Phase 2: Auth | 17 | 0 | 0% ⏳ |
| Phase 3: Dashboard | 16 | 0 | 0% ⏳ |
| Phase 4: MCP Mgmt | 22 | 0 | 0% ⏳ |
| Phase 5: User Mgmt | 19 | 0 | 0% ⏳ |
| Phase 6: Config | 20 | 0 | 0% ⏳ |
| Phase 7: Analytics | 22 | 0 | 0% ⏳ |
| Phase 8: Real-time | 19 | 0 | 0% ⏳ |
| Phase 9: Polish | 29 | 0 | 0% ⏳ |
| Phase 10: Docs/Deploy | 23 | 0 | 0% ⏳ |
| **Total** | **197** | **3** | **1.5%** |

---

## 🎯 Success Metrics

### User Experience
- [ ] Login to dashboard in <2 seconds
- [ ] Dashboard loads in <1 second after login
- [ ] Real-time updates appear within 1 second
- [ ] Smooth 60fps animations
- [ ] Works on mobile (320px width)
- [ ] Accessible (Lighthouse accessibility score >95)

### Performance
- [ ] API response time <100ms (p95)
- [ ] Database queries <50ms (p95)
- [ ] WebSocket latency <100ms
- [ ] Frontend bundle size <500KB (gzipped)
- [ ] Lighthouse performance score >90

### Reliability
- [ ] API uptime >99.9%
- [ ] Database connection pool stable
- [ ] WebSocket reconnects automatically
- [ ] No memory leaks
- [ ] Graceful error handling everywhere

### Code Quality
- [ ] Backend test coverage >80%
- [ ] Frontend test coverage >80%
- [ ] No critical security vulnerabilities
- [ ] ESLint/Pylint passing
- [ ] Type safety (TypeScript strict mode)

---

## 🚀 Quick Start (After Phase 1)

```bash
# Clone repository
git clone <repo-url>
cd omni2-admin

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_admin.py  # Create initial admin user
uvicorn app.main:app --reload

# Frontend setup (new terminal)
cd frontend
pnpm install
pnpm dev

# Docker (alternative)
docker-compose up --build

# Access
# Frontend: http://localhost:3000
# Backend: http://localhost:8500
# API Docs: http://localhost:8500/docs
```

---

## 📝 Notes

### Design Decisions
- **Next.js App Router**: Chosen for better performance, built-in API routes, and modern patterns
- **shadcn/ui**: Chosen for customization flexibility and Radix UI primitives
- **Zustand**: Chosen over Redux for simplicity and less boilerplate
- **React Query**: Chosen for server state management and caching
- **Recharts**: Chosen for React-native charting with good defaults

### Future Enhancements (Post-MVP)
- [ ] Alert rules and notifications
- [ ] Email notifications
- [ ] Slack notifications
- [ ] Advanced search with filters
- [ ] Saved queries/dashboards
- [ ] User preferences persistence
- [ ] Audit log advanced filtering
- [ ] Cost alerts and budgets
- [ ] Scheduled reports
- [ ] MCP marketplace (install new MCPs)
- [ ] Multi-tenancy support
- [ ] SSO integration (OAuth, SAML)
- [ ] API rate limiting dashboard
- [ ] A/B testing framework
- [ ] Feature flags

### Known Limitations (MVP)
- Single admin instance (no clustering)
- No Redis caching (direct DB queries)
- No CDN for static assets
- No email service (Phase 1)
- No advanced alerting (Phase 1)
- No backup UI (manual backups)

---

## 🤝 Contributing

This is an internal project, but if you want to contribute:
1. Create a feature branch from `main`
2. Follow commit message conventions
3. Write tests for new features
4. Update documentation
5. Submit PR with detailed description

---

## 📞 Support

**Developer**: [Your Name]  
**Email**: [Your Email]  
**Slack**: #omni2-admin

---

**Last Updated**: January 6, 2026  
**Next Review**: End of Phase 1 (January 13, 2026)
