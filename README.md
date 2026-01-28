# AI-Powered Healthcare Claims Denial Prevention System

## 🎯 Problem Statement

Healthcare claim denials cost the US healthcare system over **$262 billion annually**, with denial rates climbing to 10-15% across payers. Each denied claim requires costly manual rework, appeals, and resubmissions—creating a massive administrative burden while delaying patient care reimbursements.

**The challenge:** How do you catch denial-prone claims *before* submission, when there's still time to fix issues like missing prior authorizations, coding errors, or insufficient documentation?

## ⚙️ Technical Approach

Built an **event-driven, multi-agent AI system** that combines RAG (Retrieval Augmented Generation) with rule-based analysis to predict and prevent claim denials in real-time.

### Architecture Highlights:

- 🔄 **Dual Workflow Design:** Proactive claim review workflow + reactive denial learning workflow that continuously improves the knowledge base
- 🧠 **RAG-Powered Pattern Matching:** pgvector-based semantic search finds similar historical denials using OpenAI embeddings (1536 dimensions)
- 🤖 **Multi-Agent Orchestration:** Concurrent processing nodes for code extraction, risk analysis, and recommendation generation
- ⚡ **Risk-Based Routing:** Intelligent triage (LOW → auto-approve, MEDIUM → feedback, HIGH → escalate) based on denial probability thresholds
- 🔌 **Sync/Async API:** FastAPI endpoints with Celery support for batch processing thousands of claims

### System Flow:

```
Claim → Extract Codes → RAG Retrieval → Risk Assessment (LLM) → Route by Risk
                                                                    ├─ LOW: Approve
                                                                    ├─ MEDIUM: Generate Feedback
                                                                    └─ HIGH: Escalate + Recommendations
```

## 🛠 Skills Demonstrated

| Category | Technologies |
|----------|-------------|
| AI/ML | OpenAI GPT-4o, RAG, Vector Embeddings, pydantic-ai |
| Databases | PostgreSQL, pgvector, SQLAlchemy, Alembic |
| Backend | Python, FastAPI, Celery, Redis |
| Infrastructure | Docker, Docker Compose |
| Domain | Healthcare Claims (FHIR, CPT, ICD-10, CARC codes) |

## 🔧 Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| SQLAlchemy + pgvector type casting conflicts | Used `CAST(:param AS vector)` instead of `::vector` syntax to avoid SQLAlchemy's `:param` collision |
| Router returning classes vs instances | Refactored workflow router to return instantiated nodes with `task_context` for proper state propagation |
| Cold-start knowledge base | Generated 30 synthetic denial patterns using real CARC codes and industry remediation strategies |
| Multi-format claim data | Designed schema-agnostic `ClaimEventSchema` that maps from FHIR, X12 837, or CSV sources |

## 📊 Quantifiable Results

- ⏱️ **Real-time Risk Scoring:** Sub-3-second denial probability assessment per claim
- 🎯 **Accurate Risk Detection:** 85% probability correctly assigned to claims with missing prior auth
- 📋 **Actionable Feedback:** Specific recommendations (code changes, documentation, auth steps) for medium-risk claims
- 🔄 **Continuous Learning:** Denial learning workflow stores new patterns with embeddings for future prevention

### Example Output (High-Risk Claim):

```json
{
  "risk_level": "high",
  "denial_probability": 0.85,
  "primary_risk_factors": ["missing_prior_auth", "high_cost_no_documentation"],
  "recommendation": "URGENT: Obtain prior authorization before submission"
}
```

## 🏗️ Project Structure

```
app/
├── workflows/
│   ├── claim_review_workflow.py          # Proactive prevention
│   ├── denial_learning_workflow.py       # Continuous learning
│   └── denial_prevention_workflow_nodes/ # 10 specialized nodes
├── database/
│   ├── denial_knowledge.py               # pgvector-enabled model
│   └── denial_knowledge_repository.py    # Vector similarity search
├── services/
│   └── embedding_service.py              # OpenAI embeddings wrapper
└── api/
    └── denial_prevention.py              # REST endpoints
```
