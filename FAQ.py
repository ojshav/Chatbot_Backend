import os
import time
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv

load_dotenv()

# Load API keys
os.environ['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")

# Initialize embeddings and LLM
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Llama3-8b-8192")

# Create prompt template
prompt = ChatPromptTemplate.from_template(
    """
    You are a friendly AI assistant for Scalixity, an e-commerce platform. Your goal is to provide helpful and engaging responses to user inquiries. Follow these guidelines:

    1. If the information is in the context:
       - Use the information directly and respond in a conversational manner.
       - Be concise and clear, avoiding phrases like "according to the context."

    2. If the information is NOT in the context:
       - Provide a direct, helpful answer using your knowledge.
       - Be concise and clear, and maintain a friendly tone.
       - If relevant, suggest consulting with Scalixity's team for specifics.

    3. If asked about Scalixity-specific information that's not in the context:
       - Simply state that you'll need to check with the Scalixity team for accurate information.
       - Avoid making up information about Scalixity.
    
    <context>
    {context}
    </context>
    
    Question: {input}
    
    Answer:
    """
)

def create_vector_embedding():
    try:
        # Load and process the text file
        loader = TextLoader("scalixity_faq_data.txt")
        documents = loader.load()
        
        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        texts = text_splitter.split_documents(documents)
        
       
        start_time = time.time()
        vectorstore = FAISS.from_documents(texts, embeddings)
      
        
        return vectorstore
    except Exception as e:
        print(f"Error creating vector store: {str(e)}")
        return None

def main(user_prompt):
 

    vectorstore = create_vector_embedding()
    if not vectorstore:
        return {"error": "Failed to initialize the knowledge base."}

    # Create and execute the chain
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = vectorstore.as_retriever()
    retrieval_chain = create_retrieval_chain(retriever, document_chain)

    try:
        start_time = time.time()
        response = retrieval_chain.invoke({"input": user_prompt})
        processing_time = time.time() - start_time

        return {
            "answer": response["answer"],
            "processing_time": processing_time
        }
    except Exception as e:
        return {"error": f"Error processing question: {str(e)}"}

if __name__ == "__main__":
    while True:
        user_prompt = input("\nYour question: ")
        if user_prompt.lower() == 'quit':
            print("Thank you for using Scalixity chatbot!")
            break

        response = main(user_prompt)
        print("\nAnswer:")
        print(response.get("answer", response.get("error")))
        print(f"\nProcessing time: {response.get('processing_time', 'N/A'):.2f} seconds")
