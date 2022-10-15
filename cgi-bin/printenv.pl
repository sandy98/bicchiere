#!/usr/bin/env perl
##
##  printenv -- demo CGI program which just prints its environment
##

print "HTTP/1.1 200 OK\r\n";
print "Content-type: text/html; charset=iso-8859-1\r\n";
#print "Content-type: text/html; charset=utf-8\r\n";
print "\r\n";
foreach $var (sort(keys(%ENV))) {
    $val = $ENV{$var};
    $val =~ s|\n|\\n|g;
    $val =~ s|"|\\"|g;
    print "${var} = \"${val}\"<br>";
    print "\r\n";
}


