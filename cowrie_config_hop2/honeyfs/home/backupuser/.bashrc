# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi

alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

export PATH="/usr/pgsql-14/bin:/usr/local/bin:/usr/bin:/bin"

PS1='[\u@\h \W]\$ '