#include <stdio.h>

int main(int argc, char *argv[]) {
	int nums[] = {6, 5, 4, 3, 2, 1};
    	printf("HTTP/1.1 %i %s\r\n", 200, "OK");
	printf("Content-Type: %s; charset=%s\r\n\r\n", "text/html", "utf-8");
	printf("\r\n\r\n");
    	printf("<!DOCTYPE %s>\r\n", "html");
	printf("<html lang=%s>\r\n", "it");
	printf("<head%s>\r\n", "");
	printf("<title>%s</title>\r\n", "CGI from C lang");
	printf("%s\r\n", "</head>");
	printf("%s\r\n", "<body style=\"color: red; text-align: center;\">");
	for (int i = 0; i < 6; i++) {
		printf("<h%i>Welcome to the wonderful world of CGI C!</h%i>\r\n", nums[i], nums[i]); 
	}
	printf("%s\r\n", "</body>");
	printf("%s\r\n", "</html>");
	printf("%s\r\n", "");

}
