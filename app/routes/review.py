"""
自己進化グラフ レビュー画面
GET  /review                 : pending の StagedChange を一覧表示
POST /review/<id>/approve    : 承認 → 本番 Neo4j に MERGE
POST /review/<id>/reject     : 却下

ベーシック認証で保護（.env の REVIEW_USER / REVIEW_PASSWORD）
ローカル実行専用。Render 本番には登録しない。
"""
import json
import os
import sys

from flask import Blueprint, jsonify, render_template
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash, generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agents.base import DB_NAME, get_driver

bp = Blueprint("review", __name__)
auth = HTTPBasicAuth()

USERS = {
    os.getenv("REVIEW_USER", "admin"): generate_password_hash(
        os.getenv("REVIEW_PASSWORD", "changeme")
    )
}


@auth.verify_password
def verify_password(username, password):
    if username in USERS and check_password_hash(USERS[username], password):
        return username
    return None


def apply_staged(session, action: str, payload: dict) -> None:
    if action == "create_recipe":
        session.run(
            """
            MERGE (r:Recipe {name: $name})
            SET r.description  = $description,
                r.cuisine      = $cuisine,
                r.region       = $region,
                r.season       = $season,
                r.confidence   = $confidence,
                r.needs_review = $needs_review,
                r.validated    = false,
                r.created_at   = datetime()
            """,
            name=payload.get("recipe_name", ""),
            description=payload.get("description", ""),
            cuisine=payload.get("cuisine", ""),
            region=payload.get("region", ""),
            season=payload.get("season", ""),
            confidence=payload.get("confidence", 0.0),
            needs_review=payload.get("needs_review", False),
        )
        for ing in payload.get("ingredients", []):
            session.run(
                """
                MERGE (i:Ingredient {name: $name})
                WITH i
                MATCH (r:Recipe {name: $recipe_name})
                MERGE (r)-[:USES {is_required: $req, note: $note}]->(i)
                """,
                name=ing.get("name", ""),
                recipe_name=payload.get("recipe_name", ""),
                req=ing.get("is_required", True),
                note=ing.get("note", ""),
            )
        for method in payload.get("cooking_methods", []):
            session.run(
                """
                MERGE (m:CookingMethod {name: $name})
                WITH m
                MATCH (r:Recipe {name: $recipe_name})
                MERGE (r)-[:COOKED_BY]->(m)
                """,
                name=method,
                recipe_name=payload.get("recipe_name", ""),
            )
        for intent in payload.get("intents", []):
            session.run(
                """
                MERGE (t:Intent {label: $label})
                WITH t
                MATCH (r:Recipe {name: $recipe_name})
                MERGE (r)-[:HAS_INTENT]->(t)
                """,
                label=intent,
                recipe_name=payload.get("recipe_name", ""),
            )
        chunk_id = payload.get("source_chunk_id")
        if chunk_id:
            session.run(
                """
                MATCH (c:Chunk) WHERE elementId(c) = $chunk_id
                MATCH (r:Recipe {name: $recipe_name})
                MERGE (c)-[:DESCRIBES]->(r)
                """,
                chunk_id=chunk_id,
                recipe_name=payload.get("recipe_name", ""),
            )

    elif action == "enrich_ingredient":
        session.run(
            """
            MATCH (i:Ingredient {name: $name})
            SET i.nutrition    = $nutrition,
                i.season_months = $season_months,
                i.allergens    = $allergens,
                i.enriched_at  = datetime()
            """,
            name=payload.get("name", ""),
            nutrition=json.dumps(payload.get("nutrition", {})),
            season_months=payload.get("season_months", []),
            allergens=payload.get("allergens", []),
        )

    elif action == "create_cluster":
        session.run(
            """
            MERGE (cl:Cluster {id: $cluster_id})
            SET cl.title      = $title,
                cl.summary    = $summary,
                cl.keywords   = $keywords,
                cl.created_at = datetime()
            """,
            cluster_id=payload.get("cluster_id", ""),
            title=payload.get("title", ""),
            summary=payload.get("summary", ""),
            keywords=payload.get("keywords", []),
        )
    else:
        raise ValueError(f"未知のaction: {action}")


@bp.get("/review")
@auth.login_required
def review():
    driver = get_driver()
    with driver.session(database=DB_NAME) as session:
        rows = [
            r.data()
            for r in session.run(
                """
                MATCH (x:StagedChange {status: 'pending'})
                RETURN x.id         AS id,
                       x.agent      AS agent,
                       x.action     AS action,
                       x.payload    AS payload,
                       x.confidence AS confidence,
                       x.evidence   AS evidence,
                       x.created_at AS created_at
                ORDER BY x.created_at ASC
                LIMIT 50
                """
            )
        ]
    driver.close()

    for r in rows:
        try:
            r["payload"] = json.loads(r["payload"])
        except Exception:
            r["payload"] = {}

    return render_template("review.html", rows=rows)


@bp.post("/review/<sid>/approve")
@auth.login_required
def approve(sid):
    driver = get_driver()
    try:
        with driver.session(database=DB_NAME) as session:
            rec = session.run(
                "MATCH (x:StagedChange {id: $id}) RETURN x", id=sid
            ).single()
            if not rec:
                return jsonify({"error": "not found"}), 404

            x = dict(rec["x"])
            payload = json.loads(x["payload"])
            apply_staged(session, x["action"], payload)

            session.run(
                """
                MATCH (x:StagedChange {id: $id})
                SET x.status = 'approved', x.decided_at = datetime()
                """,
                id=sid,
            )
        return jsonify({"ok": True, "action": x["action"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        driver.close()


@bp.post("/review/<sid>/reject")
@auth.login_required
def reject(sid):
    driver = get_driver()
    try:
        with driver.session(database=DB_NAME) as session:
            session.run(
                """
                MATCH (x:StagedChange {id: $id})
                SET x.status = 'rejected', x.decided_at = datetime()
                """,
                id=sid,
            )
        return jsonify({"ok": True})
    finally:
        driver.close()


@bp.get("/review/stats")
@auth.login_required
def stats():
    driver = get_driver()
    with driver.session(database=DB_NAME) as session:
        result = session.run(
            """
            MATCH (x:StagedChange)
            RETURN x.status AS status, count(x) AS count
            """
        )
        data = {r["status"]: r["count"] for r in result}
    driver.close()
    return jsonify(data)
