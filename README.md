# Alexa AI assistant

Custom Alexa skill that routes user questions to a selectable LLM provider (GitHub Copilot, ChatGPT, Claude, MistralAI, ...) and returns an answer.

You can invoke and ask in one sentence, for example:

- "Alexa, ask Neo chat how old is George Clooney"

Or you can have a real discussion with it, for example:

- "Alexa, launch Neo chat"
- "What is the age of george clooney ?"
- "How many movies did he make?"

## Features

- Support multiple providers:
    - **GitHub Copilot**
    - **ChatGPT**
    - **Claude**
    - **MistralAI**
- Support multiple languages
- Optional follow-up suggestions
- Conversation context memory in session

## Supported languages

Language currently available (In `lambda/langs/`):

- English
- German
- Spanish
- French
- Hindi
- Italian
- Japanese
- Portuguese

## Prerequisites

- Amazon Developer account: https://developer.amazon.com
- One LLM provider account and API key/token:
    - GitHub token (with `models:read` permission)
    - OpenAI API key
    - Anthropic API key
    - Mistral API key

## Step-by-step tutorial

### 1.
 Login to https://developer.amazon.com/alexa/console/ask

### 2. 
Click on "Create Skill" and name the skill "AI Assistant". Choose the primary locale according to your language.

![name your skill](images/name_your_skill.png)

### 3. 
Choose "Other" and "Custom" for the model.

![type of experience](images/type_of_experience.png)

![choose a model](images/choose_a_model.png)

### 4. 
Choose "Alexa-hosted (Python)" for the backend resources.

![hosting services](images/hosting_services.png)

### 5. 
Click on "Import Skill", paste the link of this repository (https://github.com/o0zz/alexa-assistant-ai.git) and click on "Import".

![import skill](images/import_git_skill.png)

### 6. 
In the "Build" tab, navigate to "Interaction Model" > "JSON Editor".

![change name](images/intents_json_editor.png)

### 7. 
Change the "invocationName" to "neo chat" or another preferred word for activation.

### 8. 
In the "Code" tab, navigate to the `lambda/config.py` file

- Choose one `AGENT = ...`
- Set its API token/key
- Set `ENABLE_FOLLOWUP_SUGGESTIONS` to `True` or `False`

Current examples in file:

```python
AGENT = GitHubCopilotAgent(model="gpt-4.1", api_token="...")
#AGENT = ChatGPTAgent(model="gpt-4o-mini", api_token="...")
#AGENT = ClaudeAgent(model="claude-3-5-sonnet-20241022", api_token="...")
#AGENT = MistralAI(model="mistral-small-latest", api_token="...")

ENABLE_FOLLOWUP_SUGGESTIONS = False
```

### 9. 
Click Save and Click Deploy. 
Go to "Test" section and enable "Skill testing" in "Development".

![development_enabled](images/development_enabled.png)

### 10. 
You are now ready to use your Alexa in AI Assistant mode.

## Cost notice

Using this skill can generate costs (AWS Lambda + model provider usage). Monitor your billing and quotas.
