from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
import ask_sdk_core.utils as ask_utils
import logging
import json
import re
import os
from typing import List, Tuple
from config import ENABLE_FOLLOWUP_SUGGESTIONS
from config import AGENT

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

LANGS_DIR = os.path.join(os.path.dirname(__file__), "langs")

def load_language_file(language_code: str, default_code: str = "en") -> dict:
    file_path = os.path.join(LANGS_DIR, f"{language_code}.json")
    if not os.path.isfile(file_path):
        file_path = os.path.join(LANGS_DIR, f"{default_code}.json")
    try:
        with open(file_path, "r", encoding="utf-8") as language_file:
            return json.load(language_file)
    except Exception as error:
        _LOGGER.warning(f"Unable to load language file '{file_path}': {error}")
        return {}

def get_language_texts(handler_input: HandlerInput) -> dict:
    locale = getattr(handler_input.request_envelope.request, "locale", "en-US") or "en-US"
    language_code = locale.split("-")[0].lower()
    return load_language_file(language_code, "en")

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        texts = get_language_texts(handler_input)
        speak_output = texts["launch_activated"]

        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

class AIQueryIntentHandler(AbstractRequestHandler):
    """Handler for AI Query Intent."""
    def can_handle(self, handler_input: HandlerInput) -> bool:
        intent_name = ""
        try:
            intent_name = handler_input.request_envelope.request.intent.name
        except Exception:
            return False

        supported_intents = {
            "AIPersonIntent",
            "AIHowIntent",
            "AIWhatIntent",
            "AIWhoIntent",
            "AIWhichIntent",
            "AIExplainIntent",
            "AITellMeAboutIntent",
            "AIDefineIntent",
            "AIWhenIntent",
            "AIWhereIntent",
            "AIWhyIntent",
            "AICompareIntent",
        }
        return intent_name in supported_intents

    def handle(self, handler_input: HandlerInput) -> Response:
        texts = get_language_texts(handler_input)
        intent = handler_input.request_envelope.request.intent
        slots = intent.slots or {}

        query = ""
        if "query" in slots:
            query = (slots.get("query").value or "").strip()
        elif "searchquery" in slots:
            query = (slots.get("searchquery").value or "").strip()

        prefix = texts["intent_prefixes"].get(intent.name)
        if prefix and query and not query.lower().startswith(prefix):
            query = f"{prefix} {query}"
        elif prefix and not query:
            query = prefix

        if not query:
            reprompt_text = texts["reprompt_default"]
            return handler_input.response_builder.speak(reprompt_text).ask(reprompt_text).response
        
        session_attr = handler_input.attributes_manager.session_attributes
        if "chat_history" not in session_attr:
            session_attr["chat_history"] = []
            session_attr["last_context"] = None
        
        # Process the query to determine if it's a follow-up question
        processed_query, is_followup = process_followup_question(query, session_attr.get("last_context"), texts)
        
        # Generate response with enhanced context handling
        response_data = generate_gpt_response(session_attr["chat_history"], processed_query, texts, is_followup)
        
        # Handle the response data which could be a tuple or string
        followup_questions = []
        if isinstance(response_data, tuple) and len(response_data) == 2:
            response_text = response_data[0]
            if ENABLE_FOLLOWUP_SUGGESTIONS:
                followup_questions = response_data[1] or []
        else:
            # Fallback for error cases
            response_text = str(response_data)
        
        # Store follow-up questions in the session
        session_attr["followup_questions"] = followup_questions
        
        # Update the conversation history with just the response text, not the questions
        session_attr["chat_history"].append((query, response_text))
        session_attr["last_context"] = extract_context(query, response_text)
        
        # Format the response with follow-up suggestions if available
        response = response_text
        if followup_questions and len(followup_questions) > 0:
            # Add a short pause before the suggestions
            response += " <break time=\"0.5s\"/> "
            response += texts["suggestions_intro"]
            # Join with 'or' for the last question
            if len(followup_questions) > 1:
                response += ", ".join([f"'{q}'" for q in followup_questions[:-1]])
                response += f", or '{followup_questions[-1]}'"
            else:
                response += f"'{followup_questions[0]}'"
            response += texts["suggestions_closer"]
        
        # Prepare response with reprompt that includes the follow-up questions
        reprompt_text = texts["reprompt_default"]
        if followup_questions:
            reprompt_text = texts["reprompt_with_suggestions"]
        
        return handler_input.response_builder.speak(response).ask(reprompt_text).response

class CatchAllExceptionHandler(AbstractExceptionHandler):
    """Generic error handling to capture any syntax or routing errors."""
    def can_handle(self, handler_input: HandlerInput, exception: Exception) -> bool:
        return True

    def handle(self, handler_input: HandlerInput, exception: Exception) -> Response:
        _LOGGER.error(exception, exc_info=True)

        texts = get_language_texts(handler_input)
        speak_output = texts["generic_error"]

        return handler_input.response_builder.speak(speak_output).ask(speak_output).response
class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return (ask_utils.is_intent_name("AMAZON.CancelIntent")(handler_input) or
                ask_utils.is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input: HandlerInput) -> Response:
        texts = get_language_texts(handler_input)
        speak_output = texts["stop_message"]

        return handler_input.response_builder.speak(speak_output).response

def process_followup_question(question: str, last_context: dict, texts: dict) -> Tuple[str, bool]:
    """Processes a question to determine if it's a follow-up and enhances it with context if needed"""
    is_followup = False
    
    # Check if the question matches any follow-up patterns
    for pattern in texts["followup_patterns"]:
        if re.search(pattern, question.lower()):
            is_followup = True
            break
    
    # If it's a follow-up and we have context, we don't need to modify the question
    # The context will be handled in the generate_gpt_response function
    return question, is_followup

def extract_context(question: str, response: str) -> dict:
    """Extracts the main context from a Q&A pair for future reference"""
    # This is a simple implementation that just returns the question and response
    # In a more advanced implementation, you could use NLP to extract key entities
    return {"question": question, "response": response}

def generate_followup_questions(conversation_context: list, query: str, response: str, texts: dict, count: int = 2) -> List[str]:
    """Generates concise follow-up questions based on the conversation context"""
    try:
        # Prepare a focused prompt for brief follow-ups
        messages = [
            {"role": "system", "content": texts["followup_system_prompt"]},
            {"role": "user", "content": texts["followup_user_prompt"]}
        ]
        
        # Add conversation context
        if conversation_context:
            last_q, last_a = conversation_context[-1]
            messages.append({"role": "user", "content": f"{texts['previous_question_prefix']}{last_q}"})
            messages.append({"role": "assistant", "content": last_a})
        
        messages.append({"role": "user", "content": f"{texts['current_question_prefix']}{query}"})
        messages.append({"role": "assistant", "content": response})
        messages.append({"role": "user", "content": texts["followup_questions_prompt"]})

        questions_text = AGENT.chat(messages, max_tokens=50, temperature=0.7, timeout=5).strip()
        questions = [q.strip().rstrip('?') for q in questions_text.split('|') if q.strip()]
        questions = [q for q in questions if len(q.split()) <= 4 and len(q) > 0][:count]

        if len(questions) < count:
            return [texts["fallback_followup_1"], texts["fallback_followup_2"]][:count]

        _LOGGER.info(f"Generated follow-up questions: {questions}")
        return questions
        
    except Exception as e:
        _LOGGER.error(f"Error in generate_followup_questions: {str(e)}")
        return [texts["fallback_followup_1"], texts["fallback_followup_2"]]

def generate_gpt_response(chat_history: list, new_question: str, texts: dict, is_followup: bool = False) -> Tuple[str, List[str]]:
    """Generates a GPT response to a question with enhanced context handling"""
    # Create a more informative system message based on whether this is a follow-up
    system_message = texts["response_system_prompt"]
    if is_followup:
        system_message += texts["followup_system_prompt_suffix"]
    
    messages = [{"role": "system", "content": system_message}]
    
    # Include relevant conversation history
    # For follow-ups, we include more context. For new questions, we limit to save tokens
    history_limit = 10 if not is_followup else 5
    for question, answer in chat_history[-history_limit:]:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    
    # Add the new question
    messages.append({"role": "user", "content": new_question})

    try:
        response_text = AGENT.chat(messages, max_tokens=300, temperature=0.2, timeout=10)

        followup_questions: List[str] = []
        if ENABLE_FOLLOWUP_SUGGESTIONS:
            try:
                followup_questions = generate_followup_questions(
                    chat_history + [(new_question, response_text)],
                    new_question,
                    response_text,
                    texts
                )
                _LOGGER.info(f"Generated follow-up questions: {followup_questions}")
            except Exception as e:
                _LOGGER.error(f"Error generating follow-up questions: {str(e)}")
                followup_questions = []

        return response_text, followup_questions
    except Exception as e:
        _LOGGER.error(f"Error generating response: {str(e)}")
        return f"{texts['response_error_prefix']}{str(e)}", []

class ClearContextIntentHandler(AbstractRequestHandler):
    """Handler for clearing conversation context."""
    def can_handle(self, handler_input: HandlerInput) -> bool:
        return ask_utils.is_intent_name("ClearContextIntent")(handler_input)

    def handle(self, handler_input: HandlerInput) -> Response:
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr["chat_history"] = []
        session_attr["last_context"] = None
        
        texts = get_language_texts(handler_input)
        speak_output = texts["clear_context_message"]
        
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )

sb = SkillBuilder()

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(AIQueryIntentHandler())
sb.add_request_handler(ClearContextIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
