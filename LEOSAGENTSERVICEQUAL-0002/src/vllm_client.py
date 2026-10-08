# file: src/vllm_client.py
"""
vLLM Client for Local LLM Inference

Provides a client for querying local vLLM endpoints as a replacement for OpenAI models.
"""

import requests
import json
import time
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class VLLMClient:
    """
    Client for interacting with vLLM inference server.
    
    Provides methods compatible with LangChain's message format.
    """
    
    def __init__(
        self,
        #url: str = "http://192.168.28.36:30858/v1/completions",
        url: str = "http://localhost:30858/v1/completions",
        model_name: str = "/root/.cache/huggingface/Llama-3.2-3B-Instruct",
        temperature: float = 0.7,
        max_tokens: int = 500,
        timeout: int = 120
    ):
        """
        Initialize vLLM client.
        
        Args:
            url: vLLM endpoint URL
            model_name: Path to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        """
        self.url = url
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        
        logger.info(f"Initialized vLLM client: {url} with model {model_name}")
    
    def query_vllm(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> Optional[str]:
        """
        Query the vLLM endpoint with a prompt.
        
        Args:
            prompt: The input prompt to send to the model
            max_tokens: Maximum number of tokens to generate (overrides default)
            temperature: Sampling temperature (overrides default)
        
        Returns:
            Generated text response or None if error occurs
        """
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature or self.temperature,
            "top_p": 0.9,
            "n": 1,
            "stream": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            start_time = time.time()
            response = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            end_time = time.time()
            
            response.raise_for_status()
            
            result = response.json()
            generated_text = result['choices'][0]['text']
            
            logger.info(f"vLLM response received in {end_time - start_time:.2f}s")
            
            return generated_text
        
        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {self.timeout} seconds")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to vLLM at {self.url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying vLLM: {e}")
            return None
        except KeyError as e:
            logger.error(f"Error parsing response: {e}")
            logger.debug(f"Response: {response.text if response else 'No response'}")
            return None
    
    def invoke(self, messages: List[Any]) -> 'VLLMResponse':
        """
        Invoke the model with LangChain-style messages.
        
        Args:
            messages: List of message objects (HumanMessage, SystemMessage, etc.)
        
        Returns:
            VLLMResponse object with content attribute
        """
        # Convert messages to prompt string
        prompt = self._messages_to_prompt(messages)
        
        # Query vLLM
        response_text = self.query_vllm(prompt)
        
        if response_text is None:
            response_text = "Error: Failed to get response from vLLM"
        
        return VLLMResponse(content=response_text)
    
    def _messages_to_prompt(self, messages: List[Any]) -> str:
        """
        Convert LangChain messages to Llama 3.2 chat format.
        
        Args:
            messages: List of message objects
        
        Returns:
            Formatted prompt string
        """
        prompt_parts = ["<|begin_of_text|>"]
        
        for msg in messages:
            # Extract message type and content
            if hasattr(msg, '__class__'):
                msg_type = msg.__class__.__name__
                content = msg.content if hasattr(msg, 'content') else str(msg)
            elif isinstance(msg, dict):
                msg_type = msg.get('type', 'human')
                content = msg.get('content', '')
            else:
                msg_type = 'human'
                content = str(msg)
            
            # Map to Llama format
            if 'System' in msg_type or msg_type == 'system':
                prompt_parts.append(f"<|start_header_id|>system<|end_header_id|>\n\n{content}<|eot_id|>")
            elif 'Human' in msg_type or msg_type == 'human' or msg_type == 'user':
                prompt_parts.append(f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>")
            elif 'AI' in msg_type or msg_type == 'ai' or msg_type == 'assistant':
                prompt_parts.append(f"<|start_header_id|>assistant<|end_header_id|>\n\n{content}<|eot_id|>")
            else:
                # Default to user message
                prompt_parts.append(f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>")
        
        # Add assistant header to get response
        prompt_parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
        
        return "".join(prompt_parts)


class VLLMResponse:
    """
    Response object compatible with LangChain response format.
    """
    
    def __init__(self, content: str):
        self.content = content
    
    def __str__(self):
        return self.content
    
    def __repr__(self):
        return f"VLLMResponse(content={self.content[:100]}...)"
