"""
Gradio web interface for the Cornell off-campus housing RAG system.

Run:
    python app.py
Then open http://localhost:7860 in your browser.
"""

import gradio as gr
from query import ask

EXAMPLE_QUESTIONS = [
    "What are the pros and cons of living in Collegetown vs downtown Ithaca?",
    "What should I ask a landlord before signing a lease?",
    "What do students say about living at Auden Ithaca?",
    "What neighborhoods work best for grad students without a car?",
    "What resources does Cornell offer if I have a problem with my landlord?",
]


def handle_query(question: str) -> tuple[str, str]:
    if not question.strip():
        return "", ""
    result = ask(question)
    sources_text = "\n".join(f"• {s}" for s in result["sources"])
    return result["answer"], sources_text


with gr.Blocks(title="Cornell Off-Campus Housing Guide") as demo:
    gr.Markdown(
        "# The Unofficial Cornell Off-Campus Housing Guide\n"
        "Ask questions about Ithaca neighborhoods, leases, landlords, and specific apartments. "
        "Answers are drawn from Cornell official guides and real student experiences on Reddit."
    )

    with gr.Row():
        question_box = gr.Textbox(
            label="Your question",
            placeholder="e.g. What are the pros and cons of living in Collegetown?",
            lines=2,
            scale=4,
        )
        ask_btn = gr.Button("Ask", variant="primary", scale=1, min_width=80)

    with gr.Row():
        answer_box = gr.Textbox(label="Answer", lines=10, scale=3)
        sources_box = gr.Textbox(label="Retrieved from", lines=10, scale=1)

    gr.Examples(
        examples=EXAMPLE_QUESTIONS,
        inputs=question_box,
        label="Try one of these",
    )

    ask_btn.click(handle_query, inputs=question_box, outputs=[answer_box, sources_box])
    question_box.submit(handle_query, inputs=question_box, outputs=[answer_box, sources_box])

if __name__ == "__main__":
    demo.launch()
