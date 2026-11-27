---
name: cc-datasource
description: Create, update, delete, and test CloudCanal datasources through a Console session. Use for datasource registration and connection checks.
---

# Datasource automation

Use `$CLOUDCANAL_SKILL/scripts/create_datajob.py` for datasource operations. The command name is old. It now covers datasource and job Console APIs.

## Access model

Reuse the same-origin Automation session from `login --save-cookie`. Default to Console API creation, configuration, connection checks, and readback. Use the browser's existing login only when the user explicitly requests Console page operation. Switch to OpenAPI only when the user asks for it.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" login \
  --base-url "$CC_BASE_URL" \
  --account "$CC_ACCOUNT" \
  --save-cookie "$CC_COOKIE_FILE"

python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" clusters \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE"
```

Create, update, and delete are CloudCanal console RDP endpoints. They use the cookie session. The login command uses `sm-crypto`. If it cannot find the module, set `SM_CRYPTO_NODE_MODULE_DIR` or `CLOUDCANAL_WEB_DIR`. Hand a Console identity challenge to the user.

## Create

Query the dynamic kv definitions for the datasource type before you create it.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" query-kv \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --type mysql --deploy-type SELF_MAINTENANCE
```

Create with explicit values. Test after add.

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" create \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --type mysql --host db.internal --port 3306 \
  --user "$DB_USER" --password "$DB_PASSWORD" --desc "mysql-test" \
  --cluster-id 1 --test-after-add --non-interactive
```

Use `--set KEY=VALUE` for dynamic kv configs from `query-kv`. Use `--dry-run` before a live create.

Keep secrets out of the skill directory. Prefer environment variables, a prompt that does not land in shell history, or a short-lived file outside `$CLOUDCANAL_SKILL`. That covers cookies, passwords, private keys, and payloads captured from the frontend.

An empty password is a real credential. Keep it as `""` in credential JSON and in command arguments. Do not treat it as missing. Do not fall back to a default password.

For an exact frontend replay, use the same multipart field names as the page.

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

Use `query-ds-config` for saved runtime config, such as TiDB `pdHost`, StarRocks HTTP or BE addresses, SSL, and proxy settings. Use `query-kv` for definitions before create. Treat `query-ds-kv-config` as a compatibility path unless the frontend trace uses that endpoint.

Use `--payload-json @file` when the frontend sends extra filters, such as `useVisibility` or approval metadata.

## Test and delete

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

Private or public host:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-host \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --host db.internal:3306 --host-type private --dry-run
```

Account, password, and security fields:

```bash
python3 "$CLOUDCANAL_SKILL/scripts/create_datajob.py" update-ds-account \
  --base-url "$CC_BASE_URL" --cookie-file "$CC_COOKIE_FILE" \
  --data-source-id 10 --user "$DB_USER" --password "$DB_PASSWORD" --security-type USER_PASSWD --dry-run
```

TLS and CA files use the frontend multipart names.

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

After any update, run `test`. Adding or updating is not proof of connectivity. CloudCanal has a separate test endpoint.

Oracle can use `--as-sysdba`. It appends `as SYSDBA` to the account, the same way the frontend does.

File uploads go out as `securityFile`, `clientSecurityFile`, and `secretFile`. Those names match the RDP form.

LLM datasource config is available through `query-llm-config --data-source-id ID --data-source-type TYPE`.

A frontend before-add test is separate from a saved-datasource test. Use the named `test` command after add. Use `call-service --service ccDataSourceTestConnectionBeforeAdd` only when you need the pre-add check on purpose.

When a datasource-specific frontend API is not named here, use `call-service --service ... --dry-run` with a payload derived from frontend source, types, service definitions, or dynamic WebOp. Add a named command only after the same workflow repeats. Use `call-api --path ...` only when you have a raw path.
