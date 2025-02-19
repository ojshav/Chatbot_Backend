from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
import mysql.connector
from FAQ import main as faq_main
from Shopping_assistant import (
    get_available_categories, 
    get_available_colors, 
    get_available_sizes,
    find_products
)
from langchain_community.llms import Ollama
import gc
import threading

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Create a thread-local storage
thread_local = threading.local()

def get_llm():
    """Get or create an LLM instance for the current thread."""
    if not hasattr(thread_local, "llm"):
        thread_local.llm = Ollama(
            model="gemma2:2b",
            temperature=0.7,
            num_ctx=512,  # Reduce context window
            num_thread=2,  # Limit number of threads
        )
    return thread_local.llm

def cleanup_llm():
    """Cleanup LLM resources."""
    if hasattr(thread_local, "llm"):
        del thread_local.llm
        gc.collect()

def get_db_connection():
    """Create and return a database connection."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
        return connection
    except mysql.connector.Error as e:
        print(f"Error connecting to the database: {e}")
        raise Exception(f"Database connection failed: {str(e)}")

def generate_product_pitch(product_description):
    """Generate a persuasive pitch for the product using LLM."""
    try:
        if not product_description:
            return "No product description available."
        
        # Get thread-specific LLM instance
        llm = get_llm()
            
        prompt = (f"The following is a product description extracted from an HTML page:\n\n"
          f"{product_description}\n\n"
          f"Based on this description, provide a single, concise, and compelling pitch in one sentence. "
          f"Focus on the key benefit and selling point without repeating.\n\nPitch:")

        response = llm.invoke(prompt)
        
        if not response or not isinstance(response, str):
            return "Unable to generate product pitch at this time."
            
        return response.strip()
    except Exception as e:
        print(f"Error generating pitch: {str(e)}")
        return "Error generating product pitch."
    finally:
        # Cleanup after generating pitch
        cleanup_llm()
        gc.collect()

def find_products_with_url(category_id, size_id, color_id):
    """Find products with their URL keys."""
    if not category_id or not size_id or not color_id:
        return []

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT DISTINCT 
                pf.name,
                pf.short_description,
                pf.url_key
            FROM ecommerce.product_flat pf
            JOIN ecommerce.product_categories pc 
                ON pf.product_id = pc.product_id
            JOIN ecommerce.product_attribute_values color_attr 
                ON pf.product_id = color_attr.product_id 
                AND color_attr.attribute_id = 23
                AND color_attr.integer_value = %s
            JOIN ecommerce.product_attribute_values size_attr 
                ON pf.product_id = size_attr.product_id 
                AND size_attr.attribute_id = 24
                AND size_attr.integer_value = %s
            WHERE pc.category_id = %s 
                AND pf.status = 1
            LIMIT 5;  -- Limit number of products to process
        """
        cur.execute(query, (color_id, size_id, category_id))
        return cur.fetchall()
    except Exception as e:
        print(f"Error finding products: {str(e)}")
        return []
    finally:
        cur.close()
        conn.close()

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    choice = data.get('choice')
    user_input = data.get('input', '').strip()
    base_url = data.get('base_url', 'http://kea.mywire.org:5500/')

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
                return jsonify({"content": categories})

            elif user_input == 'get_sizes':
                sizes = get_available_sizes()
                return jsonify({"content": sizes})

            elif user_input == 'get_colors':
                colors = get_available_colors()
                return jsonify({"content": colors})

            elif user_input.startswith('find_products'):
                try:
                    parts = user_input.split()
                    if len(parts) != 4:
                        return jsonify({"content": "Invalid input format. Expected: find_products category_id size_id color_id"})
                    
                    _, category, size, color = parts
                    category_id = int(category)
                    size_id = int(size)
                    color_id = int(color)
                    
                    products = find_products_with_url(category_id, size_id, color_id)
                    
                    if not products:
                        return jsonify({"content": []})

                    recommended_products = []
                    for product in products:
                        if not product.get('short_description'):
                            continue
                            
                        pitch = generate_product_pitch(product.get('short_description'))
                        product_url = f"{base_url.rstrip('/')}/{product.get('url_key', '').lstrip('/')}"
                        
                        recommended_products.append({
                            "name": product.get('name', 'Unknown Product'),
                            "description": product.get('short_description', ''),
                            "recommendation": pitch,
                            "url": product_url
                        })
                      
                        
                        # Force garbage collection after each product
                        gc.collect()

                    return jsonify({"content": recommended_products})
                    
                except ValueError:
                    return jsonify({"content": "Invalid ID format. Please provide numeric IDs."})
                except Exception as e:
                    print(f"Error processing products: {str(e)}")
                    return jsonify({"content": f"Error processing products: {str(e)}"})

            else:
                return jsonify({"content": "Invalid shopping assistant command."})
        
        else:
            return jsonify({"content": "Invalid choice. Please select a valid option."})

    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({"content": f"Error: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)