---
name: cc-datasource
description: Create, update, delete, and test CloudCanal datasources through a Console session. Use for datasource registration, not for creating jobs or N×N batch tests.
---

# Datasource Automation

Use the bundled `$CLOUDCANAL_SKILL/scripts/create_datajob.py` command for datasource operations. The command name is historical; it now covers datasource and job console APIs.

## Access Model

Use the existing Console session for datasource work. Switch to OpenAPI only when the user explicitly requests it. If the session is missing, the user can run the first command to sign in. Use the second command to check the session.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" login \
  --base-url "$CC_BASE_URL" \
  --account "$CC_ACCOUNT" \
  --save-cookie "$CC_COOKIE_FILE"

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" clusters \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
```

The datasource create/update/delete endpoints are CloudCanal console RDP endpoints, authenticated by cookie/session. The Automation login command uses `sm-crypto`. If it cannot locate the module, set `SM_CRYPTO_NODE_MODULE_DIR` or `CLOUDCANAL_WEB_DIR`. Hand off any Console identity challenge to the user.

## Create

Always query dynamic kv definitions for the datasource type before creating:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-kv \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --type mysql --deploy-type SELF_MAINTENANCE
```

Create with explicit values and test after add:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --type mysql --host db.internal --port 3306 \
  --user "$DB_USER" --password "$DB_PASSWORD" --desc "mysql-test" \
  --cluster-id 1 --test-after-add --non-interactive
```

Use `--set KEY=VALUE` for dynamic kv configs returned by `query-kv`. Use `--dry-run` before live creation.

Keep secrets out of the skill directory. Prefer environment variables, shell history-safe prompts, or short-lived files outside `$CLOUDCANAL_SKILL` for cookies, passwords, private keys, and frontend-captured payloads.

An empty password is a real credential value. Preserve it as `""` in credential JSON and command arguments; do not treat it as missing and fall back to a default password.

For exact frontend replay, use the same multipart field names as the page:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" call-service \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --service rdpDataSourceAdd \
  --multipart --payload-part-name DataSourceAddData \
  --payload-json @DataSourceAddData.json \
  --file-part securityFile=/path/to/ca.pem \
  --file-part clientSecurityFile=/path/to/client.pem \
  --file-part secretFile=/path/to/keytab \
  --dry-run
```

## Query

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" list-ds \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --type mysql

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-ds \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-ds-config \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-ds-kv-config \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10
```

Use `query-ds-config` for saved runtime datasource config such as TiDB `pdHost`, StarRocks HTTP/BE addresses, SSL, and proxy settings. Use `query-kv` for before-create definitions. Treat `query-ds-kv-config` as legacy/compatibility unless the frontend trace shows that exact endpoint.

Use `--payload-json @file` when the frontend sends extra filters, such as `useVisibility` or approval metadata.

## Test And Delete

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" test \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --cluster-id 1 --non-interactive

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" delete \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --yes
```

## Update

Description:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-desc \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --desc "new desc" --dry-run
```

Private/public host:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-host \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --host db.internal:3306 --host-type private --dry-run
```

Account/password/security fields:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-account \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --user "$DB_USER" --password "$DB_PASSWORD" --security-type USER_PASSWD --dry-run
```

TLS/CA file fields follow the frontend multipart names:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-account \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --user "$DB_USER" --password "$DB_PASSWORD" \
  --security-file /path/to/truststore.jks \
  --client-security-file /path/to/keystore.jks \
  --secret-file /path/to/client.crt \
  --dry-run
```

Dynamic kv config:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" upsert-ds-config \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --set useSSL=false --dry-run
```

## Notes

- After any update, run `test`; CloudCanal has a separate test endpoint, and adding/updating is not itself proof of connectivity.
- Oracle can use `--as-sysdba`; it appends `as SYSDBA` to the account like the frontend.
- File uploads are sent as `securityFile`, `clientSecurityFile`, and `secretFile`, matching the RDP frontend form.
- LLM datasource configs are available through `query-llm-config --data-source-id ID --data-source-type TYPE`.
- Frontend before-add tests are separate from saved-datasource tests. Use named `test` after add; use `call-service --service ccDataSourceTestConnectionBeforeAdd` only when you intentionally need pre-add validation.
- If a datasource-specific frontend API is not named here yet, use `call-service --service ... --dry-run` with the browser-captured payload, then add a named command only after the workflow is repeated. Use `call-api --path ...` only when you have a raw path.
