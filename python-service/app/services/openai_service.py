"""
OpenAI integration service for AI operations with failover support
"""

import json
import logging
from functools import lru_cache
from typing import List, Dict, Any, Optional

import openai
import tiktoken

from app.core.config import settings
from app.services.ai_failover_service import ai_failover_service, ModelTier

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions with AI model failover"""

    def __init__(self):
        # Initialize embedding service using factory
        from app.services.embedding.embedding_factory import EmbeddingServiceFactory

        self.embedding_service = EmbeddingServiceFactory.get_embedding_service_sync()
        logger.info("Using embedding service from factory")

        # Use AI failover service for text generation
        self.failover_service = ai_failover_service

        # Fallback settings for non-failover methods
        self.model = settings.OPENAI_MODEL
        self.vision_model = "gpt-4-vision-preview"

    @lru_cache(maxsize=1)
    def _get_tokenizer(self, model: str):
        """Get tokenizer for the model"""
        try:
            return tiktoken.encoding_for_model(model)
        except Exception:
            return tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in text"""
        model = model or self.model
        encoding = self._get_tokenizer(model)
        return len(encoding.encode(text))

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text - now delegates to embedding service"""
        try:
            return await self.embedding_service.create_embedding(text)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts - now delegates to embedding service"""
        try:
            return await self.embedding_service.create_embeddings(texts)
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        preferred_tier: Optional[ModelTier] = None,
        supports_vision: Optional[bool] = None,
        supports_function_calling: Optional[bool] = None,
    ):
        """Generate chat completion with AI model failover"""
        temperature = temperature if temperature is not None else settings.TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS

        try:
            # Use failover service for robust completion
            result = await self.failover_service.chat_completion_with_failover(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                required_tier=preferred_tier,
                supports_vision=supports_vision,
                supports_function_calling=supports_function_calling,
            )

            return result

        except Exception as e:
            logger.error(f"Error in chat completion with failover: {str(e)}")
            raise

    async def analyze_excel_content(
        self, excel_data: Dict[str, Any], user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Excel content using AI"""

        # Prepare the context
        context = self._prepare_excel_context(excel_data)

        # Create the prompt
        system_message = (
            "You are an Excel expert assistant. Analyze the provided Excel data "
            "and provide insights, identify issues, and suggest improvements. Focus on:\n"
            "1. Data quality issues\n"
            "2. Formula errors or inefficiencies\n"
            "3. Structure and organization problems\n"
            "4. Best practices violations\n"
            "5. Optimization opportunities"
        )

        user_message = f"Excel Data Context:\n{context}"
        if user_query:
            user_message += f"\n\nUser Question: {user_query}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        # Get AI analysis with failover (prefer premium models for analysis)
        analysis = await self.chat_completion(
            messages, preferred_tier=ModelTier.PREMIUM
        )

        # Get model info from failover service
        model_status = self.failover_service.get_system_status()
        active_model = "unknown"
        if model_status["healthy_models"] > 0:
            for model_key, model_info in model_status["models"].items():
                if model_info["is_healthy"]:
                    active_model = model_key
                    break

        return {
            "analysis": analysis,
            "context_tokens": self.count_tokens(context),
            "model_used": active_model,
            "failover_status": {
                "healthy_models": model_status["healthy_models"],
                "total_models": model_status["total_models"],
            },
        }

    async def generate_excel_solution(
        self, problem_description: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Excel solution for a problem"""

        system_message = (
            "You are an Excel expert. Provide detailed, step-by-step solutions "
            "for Excel problems. Include:\n"
            "1. Specific formulas with explanations\n"
            "2. Alternative approaches if applicable\n"
            "3. Best practices and tips\n"
            "4. Common pitfalls to avoid\n"
            "Format your response in clear sections with examples."
        )

        user_message = f"Problem: {problem_description}"
        if context:
            user_message += f"\n\nAdditional Context: {context}"

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        solution = await self.chat_completion(
            messages, preferred_tier=ModelTier.STANDARD
        )

        return {
            "solution": solution,
            "problem": problem_description,
            "model_used": "failover_service",
            "failover_enabled": True,
        }

    def _prepare_excel_context(self, excel_data: Dict[str, Any]) -> str:
        """Prepare Excel data context for AI analysis"""
        context_parts = []

        # Add file metadata
        if "metadata" in excel_data:
            context_parts.append(f"File Info: {excel_data['metadata']}")

        # Add sheet information
        if "sheets" in excel_data:
            for sheet_name, sheet_data in excel_data["sheets"].items():
                context_parts.append(f"\nSheet: {sheet_name}")

                # Add sample data
                if "sample_data" in sheet_data:
                    context_parts.append(f"Sample Data: {sheet_data['sample_data']}")

                # Add formulas
                if "formulas" in sheet_data:
                    context_parts.append(f"Formulas Found: {sheet_data['formulas']}")

                # Add data types
                if "data_types" in sheet_data:
                    context_parts.append(f"Column Types: {sheet_data['data_types']}")

        # Truncate if too long
        context = "\n".join(context_parts)
        max_context_tokens = settings.MAX_TOKENS // 2

        if self.count_tokens(context) > max_context_tokens:
            # Truncate to fit within token limits
            encoding = self._get_tokenizer(self.model)
            tokens = encoding.encode(context)[:max_context_tokens]
            context = encoding.decode(tokens)

        return context

    async def analyze_image(
        self, image_data: str, prompt: str, temperature: Optional[float] = None
    ) -> str:
        """Analyze image using vision models with failover"""
        try:
            # Use provided temperature or default from settings
            temp = (
                temperature if temperature is not None else settings.VISION_TEMPERATURE
            )

            # Create vision-compatible messages
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}"
                            },
                        },
                    ],
                }
            ]

            # Use failover service with vision support requirement
            result = await self.failover_service.chat_completion_with_failover(
                messages=messages,
                temperature=temp,
                max_tokens=2000,
                supports_vision=True,  # Require vision support
            )

            return result

        except Exception as e:
            logger.error(f"Error analyzing image with failover: {str(e)}")

            # Fallback to direct OpenAI call if failover fails
            try:
                logger.info("Attempting direct OpenAI fallback for image analysis")
                direct_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                response = await direct_client.chat.completions.create(
                    model=self.vision_model,
                    messages=messages,
                    temperature=temp,
                    max_tokens=2000,
                )
                return response.choices[0].message.content
            except Exception as fallback_error:
                logger.error(f"Direct OpenAI fallback also failed: {fallback_error}")
                raise e

    async def analyze_image_structured(
        self, image_data: str, prompt: str
    ) -> Dict[str, Any]:
        """Analyze image and return structured data"""
        try:
            # Add JSON format instruction to prompt
            json_prompt = (
                f"{prompt}\n\n"
                "IMPORTANT: Return ONLY valid JSON with no additional text "
                "or markdown formatting."
            )

            # Use vision model for structured data extraction
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data extraction expert. Extract structured "
                            "data from images and return valid JSON only. Do not "
                            "include any markdown formatting or additional text."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": json_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                },
                            },
                        ],
                    },
                ],
                temperature=settings.VISION_TEMPERATURE,
                max_tokens=2000,
            )

            # Parse JSON response
            content = response.choices[0].message.content

            # Remove markdown formatting if present
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Raw content: {content}")
            # Return empty structure on parse error
            return {
                "type": "unknown",
                "headers": [],
                "data": [],
                "error": "Failed to parse JSON response",
            }
        except Exception as e:
            logger.error(f"Error analyzing image for structured data: {str(e)}")
            raise

    async def parse_vba_requirements(
        self,
        description: str,
        context: Optional[Dict[str, Any]] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Parse user requirements for VBA generation"""
        try:
            system_prompt = (
                "You are a VBA code generation assistant. Analyze the user's "
                "request and extract:\n"
                "1. Main objective/purpose\n"
                "2. Data sources (worksheets, ranges)\n"
                "3. Required operations (sort, filter, calculate, etc.)\n"
                "4. Output format and destination\n"
                "5. Any specific constraints or requirements\n\n"
                "Return a structured JSON response."
            )

            user_prompt = (
                f"User request: {description}\n\n"
                f"Context: {context if context else 'No additional context'}\n"
                f"Language preference: {language}\n\n"
                "Extract the requirements for VBA code generation."
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.error(f"Error parsing VBA requirements: {str(e)}")
            raise

    async def generate_vba_code(
        self, requirements: Dict[str, Any], language: str = "en"
    ) -> str:
        """Generate VBA code based on parsed requirements"""
        try:
            system_prompt = (
                "You are an expert VBA developer. Generate clean, efficient VBA "
                "code based on the requirements.\n"
                "Include:\n"
                "- Option Explicit\n"
                "- Error handling\n"
                f"- Comments in {language}\n"
                "- Performance optimizations\n"
                "- No Select/Activate patterns\n"
                "- Proper variable declarations"
            )

            user_prompt = (
                f"Generate VBA code for:\nRequirements: {requirements}\n\n"
                "The code should be production-ready and follow best practices."
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating VBA code: {str(e)}")
            raise

    async def enhance_vba_code(
        self,
        vba_code: str,
        issues: List[Dict[str, Any]],
        suggestions: List[Dict[str, Any]],
    ) -> str:
        """Enhance existing VBA code with improvements"""
        try:
            system_prompt = (
                "You are an expert VBA developer. Enhance the provided VBA code by:\n"
                "1. Fixing identified issues\n"
                "2. Implementing suggested improvements\n"
                "3. Adding robust error handling\n"
                "4. Optimizing performance\n"
                "5. Improving code readability"
            )

            user_prompt = (
                f"Enhance this VBA code:\n\n```vba\n{vba_code}\n```\n\n"
                f"Issues found: {issues}\n"
                f"Suggestions: {suggestions}\n\n"
                "Provide the enhanced version with all improvements."
            )

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=3000,
            )

            # Extract code from response
            enhanced_code = response.choices[0].message.content
            # Remove markdown code blocks if present
            enhanced_code = (
                enhanced_code.replace("```vba", "").replace("```", "").strip()
            )

            return enhanced_code

        except Exception as e:
            logger.error(f"Error enhancing VBA code: {str(e)}")
            raise


# Create singleton instance
openai_service = OpenAIService()
