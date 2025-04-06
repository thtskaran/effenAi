from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import SKLearnVectorStore
from transformers import AutoTokenizer, AutoModel

# List of URLs to load documents from
urls = [
    "https://lilianweng.github.io/posts/2023-06-23-agent/",
    "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/",
    "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/",
]

# Load documents from the URLs
docs = [WebBaseLoader(url).load() for url in urls]
docs_list = [item for sublist in docs for item in sublist]

# Initialize a text splitter with specified chunk size and overlap
text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=250, chunk_overlap=0
)

# Split the documents into chunks
doc_splits = text_splitter.split_documents(docs_list)



# # Load the Hugging Face model and tokenizer
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


# # Function to generate embeddings
def generate_embeddings(texts):
    inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)
    embeddings = outputs.last_hidden_state.mean(dim=1).detach().numpy()
    return embeddings


# # Generate embeddings for document chunks
embeddings = generate_embeddings([doc.page_content for doc in doc_splits])

# # Create a vector store
# vectorstore = SKLearnVectorStore.from_documents(doc_splits, embeddings)
# retriever = vectorstore.as_retriever(k=4)


class CustomEmbeddingFunction:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def embed_documents(self, texts):
        return self.embeddings

    def embed_query(self, query):
        # Assuming you have a function to generate embeddings for a single query
        return generate_embeddings([query])[0]


# Generate embeddings for document chunks
embeddings = generate_embeddings([doc.page_content for doc in doc_splits])

# Create a custom embedding function
embedding_function = CustomEmbeddingFunction(embeddings)

# Create a vector store
vectorstore = SKLearnVectorStore.from_documents(doc_splits, embedding_function)
retriever = vectorstore.as_retriever(k=4)


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Define the prompt template for the LLM
prompt = PromptTemplate(
    template="""
    You are an assistant for question-answering tasks. Use the following documents to answer the question.
    If you don't know the answer, strictly mention that knowledge not available. Use three sentences maximum and keep the answer concise:
    Question: {question}
    Documents: {documents}
    Answer:
    """,
    input_variables=["question", "documents"],
)

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-001", temperature=0.2)


# Define the RAG application class
class RAGApplication:
    def __init__(self, retriever, rag_chain):
        self.retriever = retriever
        self.rag_chain = rag_chain

    def run(self, question):
        # Retrieve relevant documents
        documents = self.retriever.invoke(question)
        # Extract content from retrieved documents
        doc_texts = "\n".join([doc.page_content for doc in documents])
        # Get the answer from the language model
        answer = self.rag_chain.invoke({"question": question, "documents": doc_texts})
        return answer


# Create a chain combining the prompt template and LLM
rag_chain = prompt | llm | StrOutputParser()

# Initialize the RAG application
rag_application = RAGApplication(retriever, rag_chain)

# Example usage
question = "What is USG?"
answer = rag_application.run(question)
print("Question:", question)
print("Answer:", answer)
