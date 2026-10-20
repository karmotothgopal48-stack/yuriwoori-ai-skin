from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    anthropic_api_key: str = ""
    # Ask Yuri: Claude model and how long one reply may take before the user gets "not available"
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_timeout_seconds: float = 30.0
    environment: str = "development"
    backend_port: int = 8000
    database_url: str = ""
    # Signs customer session tokens (app/core/security.py) and report links. Must be a long random value.
    jwt_secret: str = ""
    user_token_days: int = 30  # signed-up user session lifetime

    # Comma-separated list of allowed browser origins (CORS).
    frontend_origin: str = "http://localhost:2999,http://127.0.0.1:2999,http://localhost:3000"

    # Official YuriWoori store: the product catalogue. Products, prices, availability, variants and the brand's
    # product copy are read live from its public Shopify feed and product pages (app/services/live_catalogue.py);
    # checkout opens its own Shopify cart. No credentials needed.
    yuriwoori_store_url: str = "https://yuriwoori.com"
    catalogue_cache_seconds: int = 300  # how long a read of the store feed (prices, availability) is reused
    catalogue_content_cache_seconds: int = 3600  # how long an unchanged product's page copy is reused
    catalogue_stale_grace_seconds: int = 900  # if the store can't be reached, how much longer the last copy may serve (flagged stale)
    catalogue_timeout_seconds: float = 10.0  # per request to the store

    # Shopify Storefront GraphQL API (app/services/shopify_client.py): the catalogue and the cart.
    # Works without a token; a token with the unauthenticated_read_metafields scope adds the custom
    # metafields (benefits, INCI, how to use). Empty domain = the store URL above (yuriwoori.com/api/...).
    shopify_store_domain: str = ""
    shopify_api_version: str = "2025-07"
    shopify_storefront_access_token: str = ""  # public Storefront token (X-Shopify-Storefront-Access-Token)
    shopify_storefront_private_token: str = ""  # private Storefront token (Shopify-Storefront-Private-Token), preferred server-side
    # The store's automatic discount slabs, as "min_subtotal:amount:title,..." (e.g. "2500:500:YWPL500,..."), copied
    # from Shopify admin. Shown to customers ONLY when Shopify's own pricing of their cart applies exactly the slab this
    # predicts (otherwise hidden and logged). Check them with: python scripts/check_discount_slabs.py
    store_discount_slabs: str = ""

    # Skin-analysis reports (app/services/reports.py): the public address of the frontend, used in the report
    # link sent to the customer (https in production), and how long a link stays valid.
    frontend_public_url: str = "http://localhost:2999"
    report_link_days: int = 30
    # WhatsApp delivery-status webhook (endpoints/delivery.py): verify token chosen in the Meta app, and the
    # Meta app secret used to check X-Hub-Signature-256 on every status callback.
    whatsapp_webhook_verify_token: str = ""
    whatsapp_app_secret: str = ""

    # Delivery test mode (app/services/delivery.py). While true (the default), verification codes and reports are
    # sent ONLY to the contacts listed here (comma-separated); every other customer's delivery stays pending with
    # reason "test_mode" and nothing is sent to them. Reports are never redirected. Set false to send to customers.
    delivery_test_mode: bool = True
    # Mobile (WhatsApp) verification is always required before any report is sent. With true (default) the email
    # copy also waits for an email code, so a mistyped address never receives someone's report; false sends it to the
    # address the customer entered once their mobile number is verified and they agreed to have it sent.
    email_report_requires_email_verification: bool = True
    delivery_test_emails: str = ""
    delivery_test_whatsapp: str = ""  # any format, e.g. "98765 43210" or "+91 98765 43210"
    # Where customers' replies go. Report emails carry "Reply-To: DELIVERY_REPLY_TO"; WhatsApp messages customers
    # send to the business number arrive on the webhook and are emailed to DELIVERY_REPLY_FORWARD_EMAIL.
    delivery_reply_to: str = ""
    delivery_reply_forward_email: str = ""
    # Only for scripts/check_delivery_config.py (checks that the WhatsApp templates are approved)
    whatsapp_business_account_id: str = ""

    # Sending results to the customer (app/services/delivery.py). Each channel is off until configured;
    # results only go to the user's own contact after they confirm it with a one-time code.
    # Email over SMTP (any provider: Google Workspace, Zoho, Amazon SES SMTP, SendGrid SMTP, ...)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""  # e.g. "YuriWoori <care@yuriwoori.com>" (must be allowed to send for that domain)
    smtp_security: str = "starttls"  # starttls | ssl | none
    # WhatsApp Business Platform (Cloud API). Business-initiated messages must use approved templates.
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v23.0"
    whatsapp_otp_template: str = ""  # an approved AUTHENTICATION template (copy-code button)
    whatsapp_results_template: str = ""  # an approved UTILITY template with 5 body variables (see README)
    # true when that template was approved with a DOCUMENT header: the report PDF is then sent as the document;
    # false: the message carries the secure, expiring report link only
    whatsapp_results_template_has_document: bool = False
    whatsapp_template_language: str = "en"

    # Customer follow-up spreadsheet in Google Sheets (app/services/customer_sheet.py, google_sheets.py,
    # scripts/customer_sheet.py). Off until enabled; submissions are queued in PostgreSQL either way.
    # The backend signs in as a Google Cloud service account whose JSON key is kept OUTSIDE this project.
    customer_sheet_sync_enabled: bool = False
    google_sheets_spreadsheet_id: str = ""  # from the sheet's URL: docs.google.com/spreadsheets/d/<ID>/edit
    google_sheets_worksheet_name: str = "CustomerTracking"  # the tab holding the 13 columns
    google_service_account_file: str = ""  # absolute path to the service account's JSON key (outside the project)
    google_sheets_timeout_seconds: float = 20.0

    # Legacy, unused: the earlier Microsoft Excel Online version (app/services/ms_graph.py), kept only so it can be
    # restored (README "Customer follow-up spreadsheet" > Rollback). Not read by the Google version.
    ms_graph_tenant_id: str = ""  # Directory (tenant) ID of the Microsoft 365 organisation
    ms_graph_client_id: str = ""  # Application (client) ID of the Entra app registration (public client)
    ms_graph_scopes: str = "Files.ReadWrite"  # delegated; offline_access is always added
    ms_graph_token_cache_path: str = ".secrets/ms_graph_token.json"  # backend-only, never committed
    ms_graph_timeout_seconds: float = 20.0
    customer_sheet_drive_id: str = ""  # drive that holds YuriWoori_Customer_Tracking.xlsx
    customer_sheet_item_id: str = ""  # the workbook's drive item ID
    customer_sheet_table: str = "CustomerTracking"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]


settings = Settings()
