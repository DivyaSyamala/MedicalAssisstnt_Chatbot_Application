import os
import base64
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage

load_dotenv()

class MedicalAssistant:
    def __init__(self):
        # 1. Initialize Embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        
        # 2. Connect to Database (RAG)
        self.vector_db = Chroma(
            persist_directory="./data/vector_store", 
            embedding_function=self.embeddings
        )
        
        # 3. Initialize Gemini 3 Flash (Multimodal)
        self.llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0.1)
        
        # 4. Standard RAG Prompt
        system_prompt = (
            "You are a professional Medical First Aid Assistant. "
            "Use the provided context to suggest treatments or identify symptoms. "
            "If the answer isn't in the context, advise seeing a doctor.\n\n"
            "CRITICAL: If symptoms suggest an emergency, start with 'EMERGENCY: CALL 108/102'."
            "\n\nCONTEXT:\n{context}"
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        # 5. Build Chains
        qa_chain = create_stuff_documents_chain(self.llm, prompt_template)
        self.rag_chain = create_retrieval_chain(self.vector_db.as_retriever(), qa_chain)

    def send_emergency_email(self, user_name, analysis, recipient_email):
        """Sends an automated email alert to the caretaker."""
        msg = EmailMessage()
        msg.set_content(
            f"URGENT MEDICAL ALERT for {user_name}\n\n"
            f"The AI Medical Assistant has detected potential complications in the uploaded report:\n"
            f"--- Analysis Summary ---\n{analysis}\n-----------------------\n\n"
            f"ACTION REQUIRED: Please check on the patient or contact a doctor.\n"
            f"EMERGENCY CONTACTS:\n- Ambulance: 108\n- Medical Support: 102"
        )
        
        msg['Subject'] = f"🚨 Emergency Health Alert: {user_name}"
        msg['From'] = os.getenv("EMAIL_USER")
        msg['To'] = recipient_email

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
                smtp.send_message(msg)
            return True
        except Exception as e:
            print(f"Email Error: {e}")
            return False

    def send_reset_email(self, recipient_email, reset_code):
        """Sends password reset code via email."""
        msg = EmailMessage()
        msg.set_content(
            f"Your password reset code is: {reset_code}\n\n"
            f"This code expires in 1 hour.\n\n"
            f"If you didn't request this, please ignore this email."
        )
        
        msg['Subject'] = "Password Reset Code - AI Medical Portal"
        msg['From'] = os.getenv("EMAIL_USER")
        msg['To'] = recipient_email

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_PASS"))
                smtp.send_message(msg)
            return True
        except Exception as e:
            print(f"Email Error: {e}")
            return False

    def auto_analyze(self, file):
        """
        NEW: Automatically scans the document for basic info immediately after upload.
        """
        if file is None:
            return "No file provided for scan.", False
            
        # Specific query for the automatic quick-scan
        auto_query = (
            "Perform a Quick Scan of this document. "
            "Identify: 1. Patient Name, 2. Report Type/Test, 3. Clinical findings summary. "
            "Check if any values are outside normal ranges and flag them. Keep it brief."
        )
        return self.ask(auto_query, file=file)

    def ask(self, query, file=None):
        """Handle both text queries and medical report analysis."""
        if not query or query.strip() == "":
            return "Please enter a valid medical question.", False

        try:
            if file is not None:
                file.seek(0) 
                file_bytes = file.read()
                mime_type = file.type
                response_text = self.analyze_report(query, file_bytes, mime_type)
            else:
                response = self.rag_chain.invoke({"input": query})
                response_text = str(response.get("answer", "No answer generated."))
            
            # --- COMPLICATION DETECTION LOGIC ---
            critical_keywords = ["emergency", "critical", "severe", "abnormal", "high risk", "immediately", "urgent"]
            is_complicated = any(word in response_text.lower() for word in critical_keywords)
            
            return response_text, is_complicated
            
        except Exception as e:
            return f"Error: {str(e)}", False

    def analyze_report(self, user_query, file_bytes, mime_type):
        """Analyze uploaded medical reports using Gemini's multimodal capabilities."""
        try:
            encoded_data = base64.b64encode(file_bytes).decode("utf-8")
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": f"Task: {user_query}. If there are dangerous abnormalities, explicitly state them. End with a medical disclaimer."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded_data}"},
                    },
                ]
            )
            response = self.llm.invoke([message])
            
            # Handle response extraction (string vs list)
            if hasattr(response, 'content'):
                if isinstance(response.content, list):
                    return str(response.content[0].get('text', response.content[0]))
                return str(response.content)
            
            return str(response)
            
        except Exception as e:
            return f"Report Analysis Error: {str(e)}"