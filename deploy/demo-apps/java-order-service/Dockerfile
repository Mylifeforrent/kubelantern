# 运行镜像：jar 由 deploy/scripts/02-build-images.sh 在宿主机用 Maven 构建。
# 无宿主机 Maven 时，脚本会回退到 Dockerfile.build（多阶段 Maven 构建）。
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/java-order-service-*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
