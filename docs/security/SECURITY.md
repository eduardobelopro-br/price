# Segurança

## Ameaças principais

O usuário fornece URLs arbitrárias. Portanto, SSRF é risco P0.

## SSRF

Antes e depois de redirects:

- permitir apenas `http`/`https`;
- rejeitar credenciais embutidas;
- resolver DNS;
- rejeitar loopback, link-local, private, multicast, reserved e unspecified;
- limitar redirects;
- validar cada destino do redirect;
- considerar DNS rebinding;
- bloquear portas não permitidas;
- timeout total/conexão/leitura;
- limite de bytes;
- content-type esperado.

Não confiar apenas em regex de hostname.

## Segredos

- `.env` fora do Git;
- tokens nunca em logs;
- `.env.example` sem valores reais;
- em produção usar secret manager quando disponível.

## API

- bind `127.0.0.1` por padrão;
- API key forte no MVP;
- se exposta, usar TLS/reverse proxy e autenticação adequada;
- rate limiting para checks manuais.

## Conteúdo remoto

Não executar JavaScript remoto no backend por padrão. Browser automation futura deve ficar isolada, com política própria e somente quando permitido.

## Supply chain

Fixar faixas de dependência, rodar auditoria e atualizar regularmente.

## Privacidade

Armazenar apenas dados necessários ao monitoramento. URLs podem conter identificadores; evitar registrá-las integralmente em logs se houver query sensível.
