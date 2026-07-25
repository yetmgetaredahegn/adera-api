#!/usr/bin/env bash
# Behavior proof for the mobile-alignment slice (AGENTS.md §7.5b): exercises the
# endpoints over real HTTP with a real cookie jar, the way the Flutter client
# will. Creates one throwaway org and deletes it again at the end.
# Usage: bash scripts/proof_mobile_alignment.sh [base-url]
API="${1:-http://127.0.0.1:8010}"
CJ=$(mktemp)
EMAIL="proof-$RANDOM@example.com"

# -q matters: without it psql appends its "INSERT 0 1" status line to stdout and
# `RETURNING id` comes back as "<uuid>INSERT01".
psql_q () { docker compose exec -T db psql -U adera -d adera -qtA -c "$1" | tr -d '[:space:]'; }

curl -s -c "$CJ" -o /tmp/reg.json -X POST "$API/api/v1/auth/register" \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"correct horse battery staple\",\"org_name\":\"Proof Co\",\"org_type\":\"diaspora\",\"country\":\"US\",\"timezone\":\"America/Los_Angeles\"}"
CSRF=$(awk '/adera_csrf/{print $7}' "$CJ")
ORG=$(psql_q "SELECT id FROM orgs WHERE name='Proof Co' ORDER BY created_at DESC LIMIT 1;")

echo "=== 1. GET /auth/me (org resolved by current_org, same as /matches) ==="
curl -s -b "$CJ" "$API/api/v1/auth/me"; echo

echo "=== 2. seed one match against a REAL ingested tender ==="
TENDER=$(psql_q "SELECT id FROM tenders ORDER BY created_at LIMIT 1;")
MATCH=$(psql_q "INSERT INTO matches (id,tender_id,org_id,score,state,eligibility,created_at,updated_at) VALUES (gen_random_uuid(),'$TENDER','$ORG',0.91,'new','unknown',now(),now()) RETURNING id;")
echo "match=$MATCH"

echo "=== 3. GET /matches ==="
curl -s -b "$CJ" "$API/api/v1/matches" > /tmp/m.json
python3 -c "import json;m=json.load(open('/tmp/m.json'))[0];print({k:m[k] for k in ('state','eligibility','score')});print('tender:',m['tender']['title'][:60],'| track:',m['tender']['bidding_track'],'| summary:',m['tender']['summary'])"

echo "=== 4. POST save WITHOUT X-CSRF-Token ==="
curl -s -b "$CJ" -o /tmp/csrf_fail.json -w 'status=%{http_code} type=%{content_type}\n' -X POST "$API/api/v1/matches/$MATCH/save"
cat /tmp/csrf_fail.json; echo

echo "=== 5. POST save WITH X-CSRF-Token ==="
curl -s -b "$CJ" -w 'status=%{http_code}\n' -X POST "$API/api/v1/matches/$MATCH/save" -H "X-CSRF-Token: $CSRF"

echo "=== 6. GET /matches?state=saved ==="
curl -s -b "$CJ" "$API/api/v1/matches?state=saved" > /tmp/s.json
python3 -c "import json;print([(m['state'],m['eligibility']) for m in json.load(open('/tmp/s.json'))])"

echo "=== 7. dismiss, then every listing (FR-7.3) ==="
curl -s -b "$CJ" -w 'dismiss status=%{http_code}\n' -X POST "$API/api/v1/matches/$MATCH/dismiss" -H "X-CSRF-Token: $CSRF"
for q in "" "?state=new" "?state=saved"; do
  echo "  /matches$q -> $(curl -s -b "$CJ" "$API/api/v1/matches$q")"
done
echo "  /matches?state=dismissed -> $(curl -s -b "$CJ" "$API/api/v1/matches?state=dismissed" -w ' [%{http_code}]')"
echo "  row still in db as: $(psql_q "SELECT state FROM matches WHERE id='$MATCH';")"

psql_q "DELETE FROM matches WHERE org_id='$ORG'; DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE email='$EMAIL'); DELETE FROM org_members WHERE org_id='$ORG'; DELETE FROM users WHERE email='$EMAIL'; DELETE FROM orgs WHERE id='$ORG';" > /dev/null
rm -f "$CJ"
echo "=== cleaned up ==="
