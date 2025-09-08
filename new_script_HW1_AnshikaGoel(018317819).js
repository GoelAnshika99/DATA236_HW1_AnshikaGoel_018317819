"use strict";
const validateForm = () => {
    const blogTitle = document.getElementById("blogTitle").value.trim();
    const authorName = document.getElementById("authorName").value.trim();
    const authorEmail = document.getElementById("authorEmail").value;
    const blogContent = document.getElementById("blogContent").value;
    const termsConditions = document.getElementById("termsConditions").checked;
    if (!blogTitle || !authorName || !authorEmail || !blogContent) {
        alert("All fields are required!");
        return false;
    }
    if (blogContent.length <= 25) {
        alert("Blog content should be more than 25 characters");
        return false;
    }
    if (!termsConditions) {
        alert("You must agree to the terms and conditions");
        return false;
    }
    return true;
};
const submissionCounter = (() => {
    let count = 0;
    return () => ++count;
})();
document.getElementById("myForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    const title = document.getElementById("blogTitle").value.trim();
    const author = document.getElementById("authorName").value.trim();
    const email = document.getElementById("authorEmail").value;
    const content = document.getElementById("blogContent").value;
    const blogData = { title, author, email, content, submissionDate: new Date().toISOString() };
    const jsonSubmissionData = JSON.stringify(blogData);
    console.log("Submission Data (String):", jsonSubmissionData);
    const parsedSubmissionData = JSON.parse(jsonSubmissionData);
    console.log("Submission Data (JSON):", parsedSubmissionData);
    const {title: blogTitle, author: authorName, email: authorEmail, content:blogContent} = parsedSubmissionData;
    console.log("Blog Title:", blogTitle);
    console.log("Author Name:", authorName);
    console.log("Author Email:", authorEmail);
    console.log("Blog Content:", blogContent);
    const currentCount = submissionCounter();
    const updatedSubmission = { ...parsedSubmissionData, id: `submission-${currentCount}` };
    console.log("Submission Counter:", currentCount);
    console.log("Updated Submission:", updatedSubmission);
    document.getElementById("myForm").reset();
});