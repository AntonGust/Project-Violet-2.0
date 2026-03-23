FROM kalilinux/kali-rolling

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        openssh-server \
        kali-linux-headless \
        sshpass 

RUN echo 'root:toor' | chpasswd

RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
RUN sudo locale-gen

# Extract rockyou.txt from the gzip file
RUN gzip -d /usr/share/wordlists/rockyou.txt.gz

# Expose custom SSH port
EXPOSE 3022

# Configure SSH to run on port 3022
RUN sed -i 's/#Port 22/Port 3022/' /etc/ssh/sshd_config && \
    sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin yes/PermitRootLogin yes/' /etc/ssh/sshd_config

# Start SSH on container start
CMD ["/usr/sbin/sshd", "-D"]