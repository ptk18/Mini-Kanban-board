# Mini Kanban Board - MVP Specification

## 1. Project Overview

A minimal, dark-themed, AI-powered Kanban project management web app for general-purpose use.

The MVP focuses on:
- Multiple personal/team boards
- Custom Kanban columns
- Standard task management
- Basic collaboration (shared boards, invite links)
- Embedded AI actions on cards
- Simple project dashboard

The goal is to build a polished, portfolio-ready MVP without expanding into a full project-management suite.

Scope was cut on 2026-09-18 to keep the backlog at ~19 issues: real-time updates, the activity log, the board-level AI assistant and the profile/settings page moved to §18. The original wording is in git history.

## 2. Target Users

**General-purpose Kanban users**

The tool should work for:
- Personal projects
- Software projects
- Study projects
- Small team projects
- General task/project management

## 3. Core Product Scope

### 3.1 Accounts

Simple accounts with:
- Sign up
- Login
- Logout (button in the app header; no separate profile/settings page)
- JWT authentication
- Email/password authentication

### 3.2 Boards

Users can:
- Create multiple boards
- View their boards
- Open a board
- Rename a board
- Delete a board
- Invite other users
- Manage board membership

Board deletion: Owner only.

Board visibility: Private by default; accessible only to owner and invited members.

### 3.3 Board Columns

Default columns:
1. To Do
2. In Progress
3. Done

Users can:
- Create custom columns
- Rename columns
- Delete columns
- Reorder columns

### 3.4 Cards

Standard card fields:
- Title
- Description
- Status / column
- Priority
- Due date
- Assignee
- Labels / tags
- Checklist
- Comments
- Parent card reference (optional)
- Created timestamp
- Updated timestamp

Card movement:
- Drag and drop
- Status dropdown

Card ordering: Manual drag and drop.

Card detail: Modal.

Card editing: Anyone on the board.

Card deletion: Anyone who can edit the board.

### 3.5 Checklists

Basic checklist functionality:
- Add checklist item
- Remove checklist item
- Edit checklist item
- Check/uncheck item

No nested checklist items.

### 3.6 Comments

Basic text comments only.

Each comment should include:
- Author
- Content
- Created timestamp

No reactions, @mentions, rich text, or attachments.

## 4. Collaboration

### 4.1 Board Invitations

Owner can invite users using an email address and generated invitation link.

Selected MVP behavior: permanent invite link.

### 4.2 Board Roles

Two roles:

#### Owner
Can:
- Edit board
- Delete board
- Manage members
- Create/edit/delete columns
- Edit cards
- Delete cards

#### Member
Can:
- View board
- Edit cards
- Move cards
- Create cards
- Delete cards
- Comment
- Use AI features

No advanced permission system in MVP.

## 5. Keeping the Board Fresh

**No WebSockets in the MVP** (descoped, see §18).

The frontend refetches board data after each of its own mutations and when the browser tab regains focus. Another member's change appears on the next refetch or a manual refresh; that is acceptable for the MVP.

## 6. Task Organization

### Search
Search title and description.

### Filters
Filter by:
- Status (column)
- Priority
- Assignee

Filters combine with AND. No label or due-date filters, no saved filters, no advanced query builder.

## 7. Dashboard

Use a **simple project dashboard**.

Show:
- Total task count
- Tasks by status
- Overdue tasks
- Progress percentage

Avoid activity timelines, completion trend charts, complex analytics, and advanced reporting.

The Kanban board remains the primary workspace.

## 8. Activity Log

**Descoped** (see §18). The `Activity` table stays in the schema because it already shipped with the data layer, but nothing writes to it or reads from it in the MVP. The dashboard (§7) is the only progress view.

# 9. AI Features

AI provider: **Google Gemini API**.

AI is integrated directly into the Kanban experience.

## 9.1 AI Card Actions

Each card can expose 5 AI actions:
1. Break down
2. Improve
3. Prioritize
4. Estimate effort
5. Summarize

AI context: **Current card only**.

AI response format: **Natural language**.

## 9.2 AI Changes

AI should never silently modify a card.

Flow:
1. User selects AI action
2. AI generates suggestion
3. User sees preview
4. User approves
5. Application updates the card

## 9.3 AI Task Breakdown

When the user selects **Break down**:
1. AI analyzes the current card
2. AI proposes child tasks
3. User reviews the proposed tasks
4. User approves
5. Child cards are created

Relationship model: **Parent -> Child only**.

## 9.4 AI Effort Estimation

AI estimates both:
- Size: Small / Medium / Large
- Time: e.g. 2 hours / 1 day / 3 days

Result is presented for approval before being applied.

## 9.5 AI Prioritization

AI proposes priority using available card context such as urgency, due date, effort, and parent/child context where available.

It proposes a priority rather than silently changing it.

## 9.6 AI Task Creation

Users can enter natural language to create a task.

Flow:
1. User enters natural-language task request
2. AI generates card
3. User previews it
4. User approves
5. Card is created

## 9.7 Project Assistant

**Descoped** (see §18). The five card actions in §9.1 and natural-language task creation in §9.6 are the whole AI surface of the MVP.

# 10. UI / UX

Visual direction: **Dark developer tool + minimal**.

Design characteristics:
- Dark theme
- Minimal visual noise
- Developer-tool aesthetic
- Clear typography
- Compact cards
- Strong keyboard/mouse usability
- Simple navigation
- Minimal animations

Primary screens:
1. Login
2. Sign up
3. Board list
4. Board
5. Card modal
6. Dashboard
7. Invitation flow

The board is the primary screen.

# 11. Technology Stack

## Frontend
- Next.js
- TypeScript
- Tailwind CSS

## Backend
- FastAPI
- Python

## Database
- SQLite

## ORM
- SQLAlchemy

Database approach: **SQLAlchemy only**, no Alembic migration system for the MVP.

## Authentication
- JWT
- Email/password

## AI
- Google Gemini API

## Deployment
**Local only for MVP**.

# 12. Suggested Architecture

```text
mini-kanban/
├── frontend/
│   ├── Next.js
│   ├── TypeScript
│   ├── Tailwind CSS
│   └── UI components
│
├── backend/
│   ├── FastAPI
│   ├── SQLAlchemy
│   ├── JWT authentication
│   ├── Gemini integration
│   ├── API routes
│   └── tests/
│
├── database/
│   └── SQLite
│
└── README.md
```

Recommended backend separation:

```text
backend/
└── app/
    ├── main.py
    ├── database.py
    ├── models/
    ├── schemas/
    ├── routers/
    ├── services/
    │   ├── auth.py
    │   ├── ai.py
    │   ├── boards.py
    │   └── cards.py
    └── scripts/
```

# 13. Core Data Models

## User
- id
- email
- password_hash
- display_name
- created_at

## Board
- id
- name
- owner_id
- created_at
- updated_at

## BoardMember
- id
- board_id
- user_id
- role
- created_at

Roles: owner, member.

## Column
- id
- board_id
- name
- position
- created_at

## Card
- id
- board_id
- column_id
- parent_card_id (nullable)
- title
- description
- priority
- due_date
- assignee_id (nullable)
- position
- created_at
- updated_at

## Label
- id
- board_id
- name

## CardLabel
- card_id
- label_id

## ChecklistItem
- id
- card_id
- content
- completed
- position

## Comment
- id
- card_id
- user_id
- content
- created_at
- updated_at

## Activity
- id
- board_id
- user_id
- card_id (nullable)
- action
- created_at

# 14. Main API Areas

## Authentication
```text
POST /auth/signup
POST /auth/login
GET  /auth/me
```

## Boards
```text
GET    /boards
POST   /boards
GET    /boards/{board_id}
PATCH  /boards/{board_id}
DELETE /boards/{board_id}
```

## Columns
```text
POST   /boards/{board_id}/columns
PATCH  /columns/{column_id}
DELETE /columns/{column_id}
```

## Cards
```text
POST   /boards/{board_id}/cards
GET    /boards/{board_id}/cards
GET    /cards/{card_id}
PATCH  /cards/{card_id}
DELETE /cards/{card_id}
```

## Comments
```text
POST   /cards/{card_id}/comments
GET    /cards/{card_id}/comments
PATCH  /comments/{comment_id}
DELETE /comments/{comment_id}
```

## AI
```text
POST /ai/card/{card_id}/breakdown
POST /ai/card/{card_id}/improve
POST /ai/card/{card_id}/prioritize
POST /ai/card/{card_id}/estimate
POST /ai/card/{card_id}/summarize
POST /ai/create-task
```

AI endpoints should return suggestions/previews rather than silently modifying data.

# 15. Dashboard Calculations

### Total tasks
`total_cards`

### Tasks by status
Cards grouped by column.

### Overdue tasks
```text
due_date < current_time
AND status != Done
```

### Progress
```text
completed_cards / total_cards * 100
```

Keep calculations simple.

# 16. Seed Data

Create one realistic demo project.

Example project: **Insurance Policy Automation**.

Suggested columns:
- Backlog
- To Do
- In Progress
- Review
- Done

Include:
- Multiple realistic cards
- Different priorities
- Due dates
- Labels
- Assignees
- Checklists
- Comments
- Parent/child cards

The seed project should demonstrate the AI features naturally.

# 17. Testing

Testing level: **Solid**.

Backend:
- Unit tests
- API tests
- Authentication tests
- Board permission tests
- Card CRUD tests
- AI endpoint tests where practical

Frontend:
- Key component tests
- Important user-flow tests

Focus on core business logic rather than a specific coverage percentage.

# 18. Explicitly Out of Scope

Do NOT implement these in the MVP:

### Descoped on 2026-09-18 (backlog reduction)
- Real-time updates over WebSockets — the frontend refetches instead (§5)
- Activity log endpoints and view — the `Activity` table stays unused (§8)
- Board-level AI project assistant (§9.7)
- Profile/settings page — logout lives in the header (§3.1)
- Label and due-date filters (§6)

### Collaboration
- Advanced roles
- Granular permissions
- Presence indicators
- Live cursors

### Notifications
- No in-app notifications
- No email notifications
- No push notifications

### Files
- No attachments
- No image uploads
- No file previews

### Dependencies
- No general task dependencies
- No dependency graph
- No blocking relationships

Only parent -> child relationships are supported.

### Project management
- No time tracking
- No recurring tasks
- No milestones
- No Gantt chart
- No calendar view
- No workload management
- No advanced reporting

### AI
- No autonomous agents
- No automatic task movement
- No automatic task creation without approval
- No full-board autonomous reasoning
- No persistent AI memory
- No multi-agent workflows
- No model-routing system

### Deployment
- No cloud deployment requirement
- No production infrastructure

### Advanced search
- No saved searches
- No advanced query builder

# 19. MVP Success Criteria

The MVP is complete when a user can:

1. Sign up
2. Log in
3. Create a board
4. Create/customize columns
5. Create cards
6. Edit cards
7. Drag cards between columns
8. Reorder cards
9. Add labels
10. Set priority
11. Set due dates
12. Assign users
13. Add checklists
14. Add comments
15. Search and filter cards
16. Invite another user with a permanent invite link
17. View the simple dashboard
18. Use AI card actions
19. Preview AI changes before applying them
20. Generate child cards from a parent task
21. Generate effort estimates
22. Generate task cards from natural language
23. Run the application locally with Next.js + FastAPI + SQLite

# 20. Product Principle

> A lightweight Kanban board for developers and small teams, with practical AI assistance built directly into the task workflow.

Prioritize:
- Working software
- Clean UX
- Clear architecture
- Useful AI integration
- Real-time collaboration
- Testability

Avoid feature creep.
