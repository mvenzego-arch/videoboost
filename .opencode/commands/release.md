---
description: Готовит версию — qa, смоук, perf, сборка exe и чеклист выкладки
agent: release-keeper
---

Версия: $ARGUMENTS

Прогоняй цепочку: `qa-runner` — suite зелёным (`dotnet test`); `smoke-tester` — `dotnet build`/`dotnet publish`, старт exe без крэша, журналы и чистый temp; `perf-guardian` — VRAM/время на RX 570 4 ГБ. После их отчётов — решение о виде дистрибутива (framework-dependent vs self-contained), сборка и свой чеклист. Любой красный пункт останавливает выкладку: докладывай мне, не тянись дальше без решения.
