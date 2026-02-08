export default function About() {
  return (
    <article className="post">
      <h1>About Me</h1>
      <hr />
      <p>
        I'm <strong>Alejandro</strong>, a Site Reliability Engineer (SRE) with a passion for
        DevOps and MLOps. I build and maintain scalable infrastructure, automate everything
        I can, and love exploring new technologies.
      </p>
      <h2>What I Do</h2>
      <ul>
        <li>Infrastructure as Code (Terraform, OpenTofu, Pulumi)</li>
        <li>Container Orchestration (Kubernetes, Docker, Podman)</li>
        <li>CI/CD Pipelines (GitLab CI, GitHub Actions)</li>
        <li>Cloud Platforms (AWS, GCP, Azure)</li>
        <li>MLOps & Data Engineering</li>
      </ul>
      <h2>This Blog</h2>
      <p>
        This is where I share my thoughts, tutorials, and learnings about technology,
        software engineering, and everything in between. Built with React, FastAPI,
        and deployed on AWS with Fedora CoreOS.
      </p>
      <h2>Connect</h2>
      <p>
        Find me on{" "}
        <a href="https://github.com/aacecandev" target="_blank" rel="noopener noreferrer">
          GitHub
        </a>{" "}
        or{" "}
        <a href="https://linkedin.com/in/aacecandev" target="_blank" rel="noopener noreferrer">
          LinkedIn
        </a>
        .
      </p>
    </article>
  );
}
