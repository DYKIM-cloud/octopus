# 파일 읽기
with open("inten.txt", "r") as infile:
    lines = infile.readlines()

# 줄바꿈 제거 + 쉼표 추가 후 다시 줄바꿈
formatted_lines = [line.strip() + ",\n" for line in lines if line.strip()]

# 결과 저장
with open("inten2.txt", "w") as outfile:
    outfile.writelines(formatted_lines)
