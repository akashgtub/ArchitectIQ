resource "kubernetes_namespace" "this" {
  metadata {
    name   = var.namespace
    labels = var.labels
  }
}

