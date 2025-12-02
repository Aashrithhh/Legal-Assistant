# import json

# json_string = '{"name": "Aashrith", "marks": [89, 76, 91]}'

# # Convert JSON string → Python dictionary
# data = json.loads(json_string)

# print(data)
# print(type(data))

# import json
# student={
#     "name":"Aashrith",
#     "marks":[89,90,91]
# }

# with open("student.json","w") as f:
#     json.dump(student,f,indent=4)

# import json 
# with open("student.json","r") as f:
#     data=json.load(f)
# print(data)

# import json

# employee = {
#     "id": 101,
#     "name": "Shivani",
#     "salary": 55000,
#     "active": True
# }

# with open("employee.json","w") as f:
#     json.dump(employee, f, indent=4)
# import json

# json_text = '{"brand": "Apple", "product": "iPhone", "price": 79999}'
# data=json.loads(json_text)

# print(data["brand"])
import json

movie = {
    "title": "Interstellar",
    "rating": 8.6,
    "genres": ["Sci-Fi", "Drama"]
}

json_str=json.dumps(movie)
print(json_str)



