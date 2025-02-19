import os
from dotenv import load_dotenv
from langchain_community.llms import Ollama
import mysql.connector
from langchain.callbacks.tracers import LangChainTracer
from langchain.callbacks.manager import CallbackManager
from langsmith import Client
from bs4 import BeautifulSoup
from langchain_groq import ChatGroq

# Load environment variables first
load_dotenv()

# Environment variables setup
POSTGRES_URL = os.getenv("MY_SQL_URL")

# Initialize LangChain tracer
tracer = LangChainTracer()
callback_manager = CallbackManager([tracer])

# Initialize LangSmith client
client = Client()
os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")
# Initialize Ollama LLM with callbacks
llm = ChatGroq(
    groq_api_key = groq_api_key,
    model="mistral",
    temperature=0.7,
    callback_manager=callback_manager
)

def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DATABASE")
        )
    except mysql.connector.Error as e:
        raise Exception(f"Database connection failed: {str(e)}")

def get_available_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT category_id, name FROM category_translations where category_id <> 1;")
        return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        print(f"Error fetching categories: {str(e)}")
        return {}
    finally:
        cur.close()
        conn.close()

def get_available_sizes():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, admin_name FROM ecommerce.attribute_options WHERE attribute_id = 24;")
        return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        print(f"Error fetching sizes: {str(e)}")
        return {}
    finally:
        cur.close()
        conn.close()

def get_available_colors():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, admin_name FROM ecommerce.attribute_options WHERE attribute_id = 23;")
        return {row[0]: row[1] for row in cur.fetchall()}
    except Exception as e:
        print(f"Error fetching colors: {str(e)}")
        return {}
    finally:
        cur.close()
        conn.close()

def find_products(category_id, size_id, color_id):
    """Find products based on category ID, size ID, and color ID."""
    if not category_id or not size_id or not color_id:
        return []

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)  # Enable fetching results as dictionaries
    try:
        # Fetch product details using the provided query
        query = """
            SELECT DISTINCT pf.* 
            FROM ecommerce.product_flat pf
            JOIN ecommerce.product_categories pc 
                ON pf.product_id = pc.product_id
            JOIN ecommerce.product_attribute_values color_attr 
                ON pf.product_id = color_attr.product_id 
                AND color_attr.attribute_id = 23  -- ID for 'color' attribute
                AND color_attr.integer_value = %s  -- Color option ID
            JOIN ecommerce.product_attribute_values size_attr 
                ON pf.product_id = size_attr.product_id 
                AND size_attr.attribute_id = 24  -- ID for 'size' attribute
                AND size_attr.integer_value = %s  -- Size option ID
            WHERE pc.category_id = %s 
                AND pf.status = 1;
        """
        # IMPORTANT: Order parameters as (color_id, size_id, category_id)
        cur.execute(query, (color_id, size_id, category_id))
        return cur.fetchall()  # Return the list of products
    except Exception as e:
        print(f"Error finding products: {str(e)}")
        return []
    finally:
        cur.close()
        conn.close()

def generate_product_pitch(product_description):
    """Generate a persuasive pitch for the product in a single response."""
    
    # Parse the HTML content
    soup = BeautifulSoup(product_description, "html.parser")
    cleaned_text = soup.get_text(separator=" ")  # Extract text from HTML
    
    # Updated prompt to ensure a single concise response
    prompt = (f"The following is a product description extracted from an HTML page:\n\n"
              f"{cleaned_text}\n\n"
              f"Based on this description, provide a single, concise, and compelling pitch in one sentence. "
              f"Focus on the key benefit and selling point without repeating.\n\nPitch:")
    
    response = llm.invoke(prompt).strip()
    
    
    # If the response contains multiple sentences, extract only the first one
    return response.split(".")[0] + "." if "." in response else response

def chat_with_assistant():
    categories = get_available_categories()
    sizes = get_available_sizes()
    colors = get_available_colors()

    print("\nAvailable product categories:")
    for cid, cname in categories.items():
        print(f"- {cname}")
    
    print("\nAvailable sizes:")
    for sid, sname in sizes.items():
        print(f"- {sname}")
    
    print("\nAvailable colors:")
    for colid, colname in colors.items():
        print(f"- {colname}")
    
    while True:
        category_input = input("\nWhich category are you interested in? (or type 'quit' to exit): ").strip()
        if category_input.lower() in ['quit', 'exit', 'bye']:
            print("Thanks for visiting! Come back anytime! 👋")
            break

        category_id = next((cid for cid, cname in categories.items() if cname.lower() == category_input.lower()), None)
        if not category_id:
            print("Invalid category. Please choose from the available options.")
            continue

        size_input = input("\nWhich size are you looking for?: ").strip()
        size_id = next((sid for sid, sname in sizes.items() if sname.lower() == size_input.lower()), None)
        if not size_id:
            print("Invalid size. Please choose from the available options.")
            continue

        color_input = input("\nWhich color do you prefer?: ").strip()
        color_id = next((colid for colid, colname in colors.items() if colname.lower() == color_input.lower()), None)
        if not color_id:
            print("Invalid color. Please choose from the available options.")
            continue

        products = find_products(category_id, size_id, color_id)
        if not products:
            print(f"No products found for {category_input} in size {size_input} and color {color_input}. 😔")
        else:
            print("\nHere are some products you might like:")
            for product in products:
                pitch = generate_product_pitch(product['description'])
                print(f"- {product['name']}")
                print(f"  Why buy this product? {pitch}\n")
        
        cont = input("\nWould you like to search again? (yes/no): ").strip().lower()
        if cont != 'yes':
            print("Thanks for shopping with us! Hope to see you again soon! 👋")
            break

if __name__ == "__main__":
    chat_with_assistant()
