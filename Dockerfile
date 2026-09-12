FROM node:20-alpine

# Lets this run on AWS Lambda (via a Function URL) without rewriting the
# app as a Lambda handler -- the adapter proxies invoke events to the
# app's normal HTTP port. Inert outside Lambda: a plain `docker run`
# ignores it entirely, since it's only invoked by the Lambda runtime.
# See infra/DESIGN.md.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY server.js ./

ENV PORT=8080
EXPOSE 8080
CMD ["node", "server.js"]
