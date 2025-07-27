"""
OpenAI integration service for AI operations
"""
import json
import openai
from typing import List, Dict, Any, Optional
import tiktoken
import logging
import asyncio
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    """Service for OpenAI API interactions"""
    
    def __init__(self):
        # Use OpenRouter if API key is available, otherwise fallback to OpenAI
        if settings.OPENROUTER_API_KEY:
            self.client = openai.AsyncOpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://excel-unified.app",
                    "X-Title": "Excel Unified"
                }
            )
            # Use Gemini models for OpenRouter
            self.model = "google/gemini-2.0-flash-exp:free"  # Free tier for general chat
            self.vision_model = "google/gemini-flash-1.5-8b"  # Vision capable model
        else:
            self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
            self.vision_model = "gpt-4-vision-preview"
        
        # Always use OpenAI for embeddings (OpenRouter doesn't support embeddings)
        self.embedding_client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL
        
    @lru_cache(maxsize=1)
    def _get_tokenizer(self, model: str):
        """Get tokenizer for the model"""
        try:
            return tiktoken.encoding_for_model(model)
        except:
            return tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in text"""
        model = model or self.model
        encoding = self._get_tokenizer(model)
        return len(encoding.encode(text))
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        try:
            # Always use OpenAI for embeddings
            response = await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            # Always use OpenAI for embeddings
            response = await self.embedding_client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ):
        """Generate chat completion"""
        temperature = temperature if temperature is not None else settings.TEMPERATURE
        max_tokens = max_tokens if max_tokens is not None else settings.MAX_TOKENS
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                return response
            else:
                return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            raise
    
    async def analyze_excel_content(
        self,
        excel_data: Dict[str, Any],
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Excel content using AI"""
        
        # Prepare the context
        context = self._prepare_excel_context(excel_data)
        
        # Create the prompt
        system_message = """You are an Excel expert assistant. Analyze the provided Excel data 
        and provide insights, identify issues, and suggest improvements. Focus on:
        1. Data quality issues
        2. Formula errors or inefficiencies
        3. Structure and organization problems
        4. Best practices violations
        5. Optimization opportunities"""
        
        user_message = f"Excel Data Context:\n{context}"
        if user_query:
            user_message += f"\n\nUser Question: {user_query}"
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # Get AI analysis
        analysis = await self.chat_completion(messages)
        
        return {
            "analysis": analysis,
            "context_tokens": self.count_tokens(context),
            "model_used": self.model
        }
    
    async def generate_excel_solution(
        self,
        problem_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate Excel solution for a problem"""
        
        system_message = """You are an Excel expert. Provide detailed, step-by-step solutions
        for Excel problems. Include:
        1. Specific formulas with explanations
        2. Alternative approaches if applicable
        3. Best practices and tips
        4. Common pitfalls to avoid
        Format your response in clear sections with examples."""
        
        user_message = f"Problem: {problem_description}"
        if context:
            user_message += f"\n\nAdditional Context: {context}"
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        solution = await self.chat_completion(messages)
        
        return {
            "solution": solution,
            "problem": problem_description,
            "model_used": self.model
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
    
    async def analyze_image(self, image_data: str, prompt: str, temperature: Optional[float] = None) -> str:
        """Analyze image using vision model with adjustable temperature"""
        try:
            # Use provided temperature or default from settings
            temp = temperature if temperature is not None else settings.VISION_TEMPERATURE
            
            # Use vision model for image analysis
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                temperature=temp,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error analyzing image: {str(e)}")
            raise
    
    async def analyze_image_structured(self, image_data: str, prompt: str) -> Dict[str, Any]:
        """Analyze image and return structured data"""
        try:
            # Add JSON format instruction to prompt
            json_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON with no additional text or markdown formatting."
            
            # Use vision model for structured data extraction
            response = await self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data extraction expert. Extract structured data from images and return valid JSON only. Do not include any markdown formatting or additional text."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": json_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                temperature=settings.VISION_TEMPERATURE,
                max_tokens=2000
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
                "error": "Failed to parse JSON response"
            }
        except Exception as e:
            logger.error(f"Error analyzing image for structured data: {str(e)}")
            raise
    
    async def parse_vba_requirements(self, description: str, context: Optional[Dict[str, Any]] = None,
                                    language: str = "en") -> Dict[str, Any]:
        """Parse user requirements for VBA generation"""
        try:
            system_prompt = """You are a VBA code generation assistant. Analyze the user's request and extract:
1. Main objective/purpose
2. Data sources (worksheets, ranges)
3. Required operations (sort, filter, calculate, etc.)
4. Output format and destination
5. Any specific constraints or requirements

Return a structured JSON response."""

            user_prompt = f"""User request: {description}
            
Context: {context if context else 'No additional context'}
Language preference: {language}

Extract the requirements for VBA code generation."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            return eval(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Error parsing VBA requirements: {str(e)}")
            raise
    
    async def generate_vba_code(self, requirements: Dict[str, Any], language: str = "en") -> str:
        """Generate VBA code based on parsed requirements"""
        try:
            system_prompt = f"""You are an expert VBA developer. Generate clean, efficient VBA code based on the requirements.
Include:
- Option Explicit
- Error handling
- Comments in {language}
- Performance optimizations
- No Select/Activate patterns
- Proper variable declarations"""

            user_prompt = f"""Generate VBA code for:
Requirements: {requirements}

The code should be production-ready and follow best practices."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating VBA code: {str(e)}")
            raise
    
    async def enhance_vba_code(self, vba_code: str, issues: List[Dict[str, Any]], 
                              suggestions: List[Dict[str, Any]]) -> str:
        """Enhance existing VBA code with improvements"""
        try:
            system_prompt = """You are an expert VBA developer. Enhance the provided VBA code by:
1. Fixing identified issues
2. Implementing suggested improvements
3. Adding robust error handling
4. Optimizing performance
5. Improving code readability"""

            user_prompt = f"""Enhance this VBA code:

```vba
{vba_code}
```

Issues found: {issues}
Suggestions: {suggestions}

Provide the enhanced version with all improvements."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=3000
            )
            
            # Extract code from response
            enhanced_code = response.choices[0].message.content
            # Remove markdown code blocks if present
            enhanced_code = enhanced_code.replace("```vba", "").replace("```", "").strip()
            
            return enhanced_code
            
        except Exception as e:
            logger.error(f"Error enhancing VBA code: {str(e)}")
            raise


# Create singleton instance
openai_service = OpenAIService()