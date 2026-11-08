resource "kubernetes_config_map" "architectiq_config" {
  metadata {
    name      = "architectiq-config"
    namespace = var.namespace
    labels    = var.labels
  }

  data = {
    ENVIRONMENT                   = var.environment
    PORT                          = "8000"
    AI_PROVIDER                   = "auto"
    ALLOW_AI_FALLBACK             = "true"
    VISION_AI_PROVIDER            = "gemini"
    TEXT_AI_PROVIDER              = "huggingface"
    HF_MODEL                      = "google/gemma-2-27b-it"
    HF_BASE_URL                   = "https://router.huggingface.co/v1"
    GEMINI_MODEL_ID               = "gemini-flash-latest"
    USE_MOCK_SIMULATOR            = "false"
    SIMULATOR_TIMEOUT_SECONDS     = "30"
    MAX_DIAGNOSTIC_EXPERIMENTS    = "3"
    INVESTIGATION_TIMEOUT_SECONDS = "60"
    MAX_MODEL_CALLS               = "5"
    CORS_ORIGINS                  = "*"
  }
}

