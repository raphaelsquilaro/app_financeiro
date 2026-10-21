# Meu financeiro

Aplicativo simples de controle financeiro feito com Python, Streamlit,
Firebase Authentication e Cloud Firestore.

## Recursos

- Cadastro e login com e-mail e senha pelo Firebase Authentication.
- Receitas e despesas vinculadas ao UID autenticado.
- Resumo de receitas, despesas e saldo.
- Criação, edição e exclusão de lançamentos.
- Valores armazenados em centavos para evitar erros de arredondamento.
- Personalização de paleta de cores com temas prontos (Verde Esmeralda, Azul Oceano, Modo Noturno, Pôr do Sol, Framboesa, Dourado e Minimalista Grafite), seletores de cores individuais, pré-visualização ao vivo e persistência automática no `.streamlit/config.toml`.

## Configuração

1. Ative o provedor **E-mail/senha** em **Firebase Console → Authentication →
   Sign-in method**.
2. Para rodar localmente, configure `.streamlit/secrets.toml` com a Web API Key
   e as credenciais Admin do Firebase. O app também aceita o JSON Admin local
   como fallback.
3. Para o Streamlit Community Cloud, cole o conteúdo de
   `.streamlit/secrets.toml` em **Manage app → Settings → Secrets**. O arquivo
   local `secrets.toml` está no `.gitignore` e não deve ser enviado ao GitHub.
4. Confirme que o Cloud Firestore está criado no banco `default`.
5. Instale as dependências e inicie o app:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\streamlit.exe run app.py
   ```

Também é possível configurar `FIREBASE_API_KEY` e
`FIREBASE_CREDENTIALS_PATH` como variáveis de ambiente. A chave Web API é usada
para chamadas de autenticação; a credencial Admin é usada somente no servidor
para acessar o Firestore. Nunca publique ou versione o arquivo Admin, a chave
privada ou o conteúdo de `secrets.toml`.

As movimentações ficam na coleção `transactions`, com o UID do Firebase
Authentication em `owner_uid`. A consulta e as operações de edição/exclusão
conferem esse UID.
