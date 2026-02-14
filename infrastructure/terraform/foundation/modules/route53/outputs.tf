output "zone_id" {
  description = "Route 53 hosted zone ID"
  value       = aws_route53_zone.main.zone_id
}

output "zone_name" {
  description = "Route 53 hosted zone name"
  value       = aws_route53_zone.main.name
}

output "name_servers" {
  description = "Name servers for DNS delegation"
  value       = aws_route53_zone.main.name_servers
}
