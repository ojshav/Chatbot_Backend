from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from FAQ import main as faq_main
from Shopping_assistant import (
    get_available_categories, 
    get_available_colors, 
    get_available_sizes,
    find_products, 
    generate_product_pitch
)
from langchain_community.llms import Ollama  # Import the LLM

# Load environment variables
load_dotenv()

# Initialize Ollama LLM
llm = Ollama(
    model="mistral",
    temperature=0.7,
)

app = Flask(__name__)
CORS(app)

def generate_product_pitch(product_description):
    """Generate a persuasive pitch for the product using LLM."""
    prompt = f"Based on the following product description, explain in 2-3 lines why someone should buy this product:\n\n{product_description}\n\nPitch:"
    response = llm(prompt)
    return response

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    choice = data.get('choice')
    user_input = data.get('input', '').strip()

    try:
        if choice == '1':  # FAQ Assistant
            response = faq_main(user_input)
            return jsonify({
                "content": response.get("answer", "Sorry, I couldn't find an answer."),
                "processing_time": response.get("processing_time", 0),
            })

        elif choice == '2':  # Shopping Assistant
            if user_input == 'get_categories':
                categories = get_available_categories()
                print(categories)
                return jsonify({"content": categories})
            

            elif user_input == 'get_sizes':
                sizes = get_available_sizes()
                print(sizes)
                return jsonify({"content": sizes})

            elif user_input == 'get_colors':
                colors = get_available_colors()
                print(colors)
                return jsonify({"content": colors})

            elif user_input.startswith('find_products'):
                
                    # Split into parts and convert to integers
                parts = user_input.split()
                if len(parts) != 4:
                    raise ValueError
                    
                _, category, size, color = parts
                category_id = int(category)
                size_id = int(size)
                color_id = int(color)
                    
                products = find_products(category_id, size_id, color_id)

                recommended_products = []
                for product in products:
                    pitch = generate_product_pitch(product['short_description'])
                    recommended_products.append({
                        "name": product['name'],
                        "recommendation": pitch,
                    })
                print(recommended_products)

                return jsonify({"content": recommended_products})

            else:
                return jsonify({"content": "Invalid shopping assistant command."})
        
        else:
            return jsonify({"content": "Invalid choice. Please select a valid option."})

    except Exception as e:
        return jsonify({"content": f"Error: {str(e)}"})

if __name__ == "__main__":
    app.run(debug=True)
