# ~/.bashrc: executed by bash(1) for non-login shells.

[ -z "$PS1" ] && return

HISTCONTROL=ignoredups:ignorespace
shopt -s histappend
HISTSIZE=2000
HISTFILESIZE=4000
shopt -s checkwinsize

PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

export LS_OPTIONS='--color=auto'
alias ls='ls $LS_OPTIONS'
alias ll='ls -alF'
alias la='ls -A'

# WordPress shortcuts
alias wp-logs='sudo tail -f /var/log/apache2/error.log'
alias wp-restart='sudo systemctl restart apache2'
alias wp-deploy='cd /var/www/html && git pull origin main && sudo chown -R www-data:www-data .'
alias db-backup='bash ~/backup_db.sh'
alias db-connect='mysql -u wp_admin -p wordpress_prod'

export PATH="$HOME/.local/bin:$PATH"
export EDITOR=vim