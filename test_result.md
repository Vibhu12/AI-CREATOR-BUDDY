#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Session focus: Add "Connections Hub" — integrations for YouTube, Instagram,
  Stripe, PayPal with dummy/mock data (user chose "take dummy"). Also refresh
  the Pricing checkout with a realistic Stripe/PayPal checkout modal.

backend:
  - task: "Integrations Hub — per-user connections (YouTube/Instagram/Stripe/PayPal)"
    implemented: true
    working: "NA"
    file: "backend/integrations.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
            New endpoints:
              GET  /api/integrations/connections            (list of 4 providers + status)
              POST /api/integrations/{provider}/connect     (body: {account})
              POST /api/integrations/{provider}/disconnect
              GET  /api/integrations/youtube/channel        (returns real or deterministic mock)
              GET  /api/integrations/instagram/profile      (deterministic mock)
              GET  /api/integrations/stripe/status          (real via key, else mock)
              GET  /api/integrations/paypal/status          (mock)
            Connection state stored in db.connections (upsert on connect).
            All endpoints require auth via current_user dependency.

  - task: "Billing checkout session flow (Stripe + PayPal)"
    implemented: true
    working: "NA"
    file: "backend/billing.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
            Added POST /api/billing/checkout (creates cs_ session id, stores in
            db.checkout_sessions) and POST /api/billing/checkout/confirm
            (flips tier + marks session complete). Legacy /billing/upgrade
            still works. Free tier rejected at checkout.

frontend:
  - task: "Connections Hub screen (/integrations)"
    implemented: true
    working: "NA"
    file: "frontend/app/integrations.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
            New screen with 4 provider cards. Connect flow shows OAuth-style
            modal: input handle/email → 'Redirecting' → 'Authorizing' →
            'Connected' success state → auto-close. Connected providers show
            summary metrics + 'View data' button which opens a detail sheet
            showing stats + recent items (videos/reels/charges/transactions).
            Disconnect uses Alert confirmation.

  - task: "Pricing checkout modal (Stripe/PayPal selection)"
    implemented: true
    working: "NA"
    file: "frontend/app/pricing.tsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
            Rewrote pricing to open a checkout modal on Upgrade tap. Modal
            shows payment method radio (Stripe/PayPal), 'Pay securely' CTA,
            then processing state with session id, then success confetti.
            Free tier cannot be checked out. Current tier button disabled.

  - task: "Profile 'Connected integrations' summary + link to hub"
    implemented: true
    working: "NA"
    file: "frontend/app/(tabs)/profile.tsx"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: |
            Replaced the per-integration rows with a compact 'X of 4
            connected' summary card that pushes to /integrations. Uses
            api.connections() instead of separate stripeStatus call.

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 11
  run_ui: false

test_plan:
  current_focus:
    - "Integrations Hub — per-user connections (YouTube/Instagram/Stripe/PayPal)"
    - "Billing checkout session flow (Stripe + PayPal)"
    - "Connections Hub screen (/integrations)"
    - "Pricing checkout modal (Stripe/PayPal selection)"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
        Implemented Option C (dummy data integrations). Please test:
        1. Backend: /api/integrations/connections returns 4 providers; connect
           with a handle stores + returns summary; disconnect clears.
        2. Backend: /api/billing/checkout creates a session; /confirm switches
           tier. Free tier rejected. Legacy /billing/upgrade still functions.
        3. Frontend: /integrations screen — connect YouTube with e.g. '@maya'
           should show OAuth-simulation modal, complete, then show metrics.
           'View data' opens detail sheet with subs/RPM/recent videos.
        4. Frontend: Pricing → Upgrade to Pro opens checkout modal with
           Stripe/PayPal radios. Pay proceeds through processing → success →
           closes. Profile shows updated tier.
        5. Regression: existing dashboard, portfolio, ai coach, strategy,
           competitors, notifications still functional.