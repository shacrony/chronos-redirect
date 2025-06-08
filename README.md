# ChronosRedirect - Open Redirect Fuzzer

ChronosRedirect é uma ferramenta desenvolvida para identificar vulnerabilidades de Open Redirect em aplicações web. Ela é capaz de testar URLs dinamicamente com diversos payloads evasivos e classificar os resultados automaticamente em `safe`, `partial` ou `vulnerable`, com foco em evitar falsos positivos.

---

## Funcionalidades

* Substitui um marcador (por padrão `FUZZ`) em URLs por payloads maliciosos.
* Faz requisições HTTP e segue redirecionamentos automaticamente.
* Classifica cada URL testada com base no redirecionamento e/ou reflexão do payload:

  * `safe`: sem redirecionamento externo e sem reflexo do payload.
  * `partial`: payload refletido no corpo da resposta, mas sem redirecionamento externo.
  * `vulnerable`: redirecionamento real para domínio malicioso conhecido (ex: `evil.com`, `127.0.0.1`).
* Exporta resultados em CSV e JSON.
* Modo stealth para evitar detecção por WAFs.

---

## Instalação

Requisitos:

```bash
pip install aiohttp tqdm
```

---

## Uso

### Comando básico:

```bash
cat urls.txt | python3 chronos-redirect.py
```

### Com todas as opções:

```bash
cat urls.txt | python3 chronosredirect.py --stealth --output resultados.json --silent --proxy http://127.0.0.1:8080 --method GET --filter-domain evil.com
```

### Argumentos:

* `-p`, `--payloads`: Arquivo com payloads personalizados.
* `-k`, `--keyword`: Palavra-chave a ser substituída nos parâmetros (padrão: `FUZZ`).
* `-c`, `--concurrency`: Número de requisições concorrentes (padrão: 100).
* `--proxy`: Proxy HTTP para interceptar as requisições (ex: `http://127.0.0.1:8080`).
* `--stealth`: Adiciona delay aleatório entre requisições (para evitar WAF).
* `--method`: Método HTTP (GET ou POST).
* `--filter-domain`: Mostra apenas redirecionamentos para domínio especificado.
* `--output`: Exporta resultados em JSON.
* `--silent`: Oculta resultados `safe` e exibe apenas `partial` ou `vulnerable`.

---

## Exemplos de Saída

```
[VULNERABLE] https://example.com/?next=//evil.com --> https://evil.com
[PARTIAL] https://example.com/?redirect=https://evil.com%3f@legit.com --> https://example.com/?redirect=https://evil.com?@legit.com
[SAFE] https://example.com/?redirect=https://example.com --> https://example.com
```

---

## Critérios de Classificação

| Status       | Descrição                                                                      |
| ------------ | ------------------------------------------------------------------------------ |
| `safe`       | Redireciona para o mesmo domínio ou não redireciona; payload não é refletido.  |
| `partial`    | Payload é refletido no corpo da resposta, mas não há redirecionamento externo. |
| `vulnerable` | Redirecionamento externo confirmado para domínio malicioso conhecido.          |

---

## Observações

* Para testes de segurança mais realistas, utilize um servidor de coleta como `https://yourdomain.com/collect` para confirmar a execução do redirecionamento.
* Caso use o `Burp` como proxy, não esqueça de usar `--proxy http://127.0.0.1:8080`.

