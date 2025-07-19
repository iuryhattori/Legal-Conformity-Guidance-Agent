import os
from crew import Juriscrew

def run():
    path = input("Enter the path to the PDF file:\n> ")
    absolute_path = os.path.abspath(path)
    if not os.path.exists(absolute_path):
        print(f"Error: The path '{absolute_path}' does not exist.")
        return

    print("🔍 Starting legal analysis of the document...")
    inputs = {
        'info': absolute_path
    }
    result = Juriscrew().crew().kickoff(inputs=inputs)
    print("✅ Workflow completed!")
    print("Result:", result)
    

if __name__ == "__main__":
    run()