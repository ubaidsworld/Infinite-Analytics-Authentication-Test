# Infinite-Analytics-Authentication-Test  
Problem definition:   
![image](https://github.com/user-attachments/assets/0ada1452-84a1-4e23-adde-81d232964ba4)
![image](https://github.com/user-attachments/assets/cf6be09a-9743-4b12-9766-1c5a0a7e9325)
![image](https://github.com/user-attachments/assets/c2bf334c-a893-42ce-bc35-143bfd932c23)

If running individually then
pip install -r requirements.txt
run uvicorn main:app --reload

If running through docker

docker build -t app/myapp:v1 .

docker run -p 8000:8000 app/myapp:v1

The application can be viewed through URL: http://localhost:8000  
Please note: Add your own google and Facebook Authorization keys!..
